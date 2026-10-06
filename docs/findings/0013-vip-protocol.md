# Stateful VIP protocol peer

The approved device-emulation path now has a userspace peer attached to the real
SPI transport. `just probe --probe-vip-service --seconds 20 --debug-services` launches it with original VIM in a bounded
QEMU run. Normal live boot is not yet switched to this peer while its application
protocol is incomplete.

The checksum-enabled path in `IUC_SPI_ReTransmission` (0xcae4) constructs fixed
20-byte frames: little-endian message ID, one length byte, up to 16 payload bytes,
and an eight-bit sum of bytes 0 through 18 at byte 19. Control IDs 0x3c1 and 0x3c2
are ACK and NAK. Their original static frames at 0x303f0 and 0x30404 contain the
ID followed by zeros, including the checksum byte. ID zero is idle.

The peer chooses its outgoing frame before processing the simultaneous incoming
frame. It acknowledges data on the next exchange and filters the retransmission
that overlaps that ACK. It keeps its outgoing application message until ACK,
and retries on NAK. Unknown commands receive a transport acknowledgment and an
explicit `handler=unimplemented` log; no application success is fabricated.

The implemented application subset is system hello (ID 0x002, zero payload),
responded to after receiving original VIM's hello. Once that response is ACKed,
the model offers heartbeat ID 0x031 every second. It offers SPI transfer slots
through SIGIO every 100 ms. These are explicit lab scheduling intervals, not
recovered hardware timings. The model currently supports one outgoing message
at a time; timeout-based retransmission and further vehicle/TAU messages remain.

`just dev software check_vip_protocol` compiles and runs the protocol test in ARM
userspace, covering the captured 0x043 checksum sample, delayed ACK, duplicate
filtering, hello ACK/NAK, heartbeat gating, and corrupt/oversized input. This
passed before the first original-VIM probe. It does not prove application or UI
readiness; integration results must be checked separately.

The first original-VIM probe (`/software/test-1336906c`) logged `VIP communication
established`, ACKed the peer's hello, and repeatedly handled heartbeat requests.
No checksum or ACK errors were observed in that capture. Unknown GPIO commands
included 0x043, 0x050, 0x051, 0x05b, 0x04a, and 0x04b. Message 0x030 is original
VIM's host heartbeat (`vimapp_HBMsgHandler` / `vimapp_HBProcessMsg`), not an unknown
vehicle request; the service now labels it accordingly.

That probe also exposed a startup ordering error: VBS exhausted its connection
attempts before VIM started, then logged null IPC handles despite its wrapper
printing successful sends. The probe now uses `LAB_VIP_SERVICE=1` in the shared
startup script, starts VIM before the service manager, and waits for the actual
hello ACK with a ten-second bound. It does not substitute a VBS readiness flag.

The reordered probe (`/software/test-cm_tvz23`) completed the hello exchange before
service startup and delivered actual VBS commands through VIM onto SPI:
0x144 with payload 01, 0x230 with payload 00000000, and 0x1d5 with payload 1801.
The original system service still reached STARTED. VBS remained STARTING because
these application responses are unimplemented. `just test` passed after the
startup-script change. Next work is the readiness/application contract behind
those observed commands, followed by TAU/audio readiness and full UI verification.

The VBS readiness response is now modeled separately from SPI ACKs. Original
`VBS_BUS_CAN_VIM_Data_Received_Cb` (0xab90 onward) recognizes ID 0x144, wakes the
readiness condition, then passes its payload to the application callback. The
peer accepts the observed one-byte Boolean registration only after the hello
ACK, retains that state, and returns ID 0x144 with the accepted value. A pending
heartbeat is not overwritten; the readiness response waits for its ACK. The
protocol test covers that sequencing, invalid values, and pre-hello rejection.

The readiness implementation was accepted by original VBS in
`/software/test-upzic6sf`: `jciVBS` reported STARTED at guest timestamp 15.077,
while the original system service also remained STARTED. The next observed
blocker is TAU connection, with the radio service repeatedly requesting status
and the system logging `Tau connected timeout!`. `just probe --probe-vip-service --verify-vbs --seconds 20 --debug-services` now
checks original hello acceptance, VBS/system STARTED, absence of null IPC handles
or checksum/ACK errors, and clean shutdown. It does not assert full UI success.

## Next TAU contract

`vbs_radio_getTauStatus` in `libjcimod_radio.so` (0x14b18) sends ID 0x1d5 with the
little-endian requested message ID 0x195. The captured payload is `95 01`.
`MODCAN_DataReadyToParse_Private` dispatches message 0x195 to code at 0x19e44;
its entry in `VBS_PvtCanRxTable` points to `VBS_BUS_CAN_TAU_Status` (0x147e0).
The field table contains A0BE, A088, A089, A08A, A08B, A08C, A06B, each eight bits.
A08A is connection/standby status, with the vendor diagnostic explicitly naming
0=standby, 1=connected, 2=disconnected. The data parser reads a presence mask and
consumes only selected fields. A selective response for the connection field
will therefore avoid inventing destination, XM, or accessory configuration.
The exact expanded-message offsets still need verification before adding that
response. No TAU connection reply has yet been implemented.

`just probe --probe-vip-service --verify-vbs --seconds 20 --debug-services` passed in `/software/test-_7y9qzsb`, including clean guest
shutdown. The TAU payload offset was then confirmed in `VBS_BUS_CAN_EventCallback`
at 0xa6e0–0xa718: it expands ID at offset 0, length at offset 5, and payload at
offset 6. Thus the mask read at offset 6 is payload byte 0; A08A is mask bit 3.
A selective connection update is message 0x195 with payload `[0x08, state]`.
This is recovered parser evidence; the response has not yet been run through the
original services. Connection-state simulation and audio support remain next.
