# Original VIM SPI and interrupt transport

The approved path preserves original VIM and emulates its devices. `mazda_vip.ko`
registers SPI controller 1, chip select 0, and explicitly binds upstream spidev.
The original binary configures mode 3, eight-bit words, and 4 MHz. The kernel
handles the standard spidev ioctl ABI, rather than a substitute ioctl parser.

`/dev/mazda_vip_transport` connects the SPI controller to a userspace VIP model.
It permits one backend at a time. Each read returns a native little-endian header
of four uint32 values (sequence, byte length, clock Hz, SPI mode), followed by TX
bytes. A response writes that same header and the same number of RX bytes.
Transfers are limited to 4096 bytes. Short reads do not consume a request; invalid,
duplicate, expired, and stale-sequence responses are rejected. No backend returns
ENOTCONN; an unanswered transfer returns ETIMEDOUT after two seconds. The timeout
is a lab bound, not a recovered hardware timing parameter.

The module also implements `/dev/cmu_io` ioctl 0x40084300: original VIM registers
its own PID and GPIO number 42 using two signed 32-bit fields. An explicit
`VIP_RAISE_IRQ` ioctl on the backend delivers SIGIO (29). Closing the
registration releases it; the emulator does not generate unsolicited interrupts.

The backend transport header is a lab API, not a Mazda wire format. The actual
VIP framing, handshake, acknowledgments, and application messages still need a
stateful model. Registering these devices alone does not establish TAU readiness.

`just probe --verify-vip --seconds 5` exercises byte exchange through spidev, response timeouts,
stale replies, exclusive backend ownership, actual signal delivery, and cleanup.
It repeats the check after unloading and reloading the module.

Static evidence in original `vim_app`:

- `spi_setParameters` 0x14554 configures eight-bit words; globals 0x3042c and
  0x30430 hold 4000000 Hz and mode 3.
- `vimgpio_IntHandler` 0x113ac constructs PID/GPIO 42 registration; ioctl at
  0x1154c uses constant 0x40084300.
- `IUC_PostRxNotification` 0xc638 performs a 20-byte initial synchronization
  transfer, TX filled with 0xff. Its diagnostic expects zero RX during this frame.
  Further state transitions must be recovered before implementing responses.

Verification on 2026-09-09: `software-vip-test` passed twice, including module
reload, in `/software/test-m9tqz99a`. Original VIM then reported successful
`SPI_Init`, `VIMGPIO_Init`, and `VIPBUS_init` in `/software/test-v699hzpz`, reaching
`IUC_Start`. No VIP protocol backend was present in that run. `just test` passed.

`just probe --probe-vim --seconds 10 --debug-services` now also runs a bounded capture backend. Once VIM
registers its IRQ target, this diagnostic raises one explicitly logged interrupt
and captures TX bytes to the retained `vip-trace.log`; it sends no responses.
The normal live boot does not launch this diagnostic backend or inject its IRQ.

The original `cmu_io.ko` resolves the second registration field: its ioctl handler
passes that field to `gpio_request_one`; `cmu_gpio_irq` calls `send_sig_info` with
signal 29. VIM's `sighandler` at 0x10c64 likewise only posts its semaphore for 29.
An initial interpretation of the field as signal 42 was wrong and terminated VIM
when exercised. The transport and its test were corrected to GPIO 42 / SIGIO.
The earlier transport-only test did not catch that ABI mistake; original-binary
validation remains necessary.

The corrected transport passed `software-vip-test` in `/software/test-r0my4h8n`.
Original VIM validation in `/software/test-99fhqs21` confirmed `VIP IRQ detected`
and captured a real 20-byte transaction at 4 MHz / mode 3:

```
43 00 01 31 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 75
```

The capture supplied no RX response, so the two-second timeout surfaced through
original `IUC_SPI_ReTransmission`, as intended. This run uses the checksum-enabled
path, not the older all-0xff synchronization path. The last byte equals the sum
of the preceding bytes for this sample; that observation alone is not sufficient
to implement the complete checksum/ACK state machine.

Further inspection of `iuc_Rx_Process_Request` shows a 10-bit message ID in the
first little-endian halfword, a length byte at offset 2, and group mask 0x3c0.
System message 0x002 logs VIP communication established; 0x031 is the heartbeat.
These facts guide the next protocol implementation, but no readiness messages
have yet been injected or synthesized.
