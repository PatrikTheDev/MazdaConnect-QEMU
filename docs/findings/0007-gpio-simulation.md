# Stateful power and ignition GPIO simulation

The approved guest module `mazda_gpio` uses the pinned Linux 6.1.0-50-armmp kernel's
gpiolib, rather than placing ordinary files under `/sys`. It exports the names
used by the original BLM_SYSTEM binary and supplies IRQ-backed sysfs edge
notifications. The kernel implements the `direction`, `value`, `edge`, and
`active_low` interfaces. A line change raises a simulated IRQ only when its
configured edge matches; writing the same value does not raise an edge.

The named sysfs exports use the upstream kernel's `gpio_chip.names` support.
See [Linux 6.1 gpiolib sysfs implementation](https://github.com/torvalds/linux/blob/v6.1/drivers/gpio/gpiolib-sysfs.c).

| Line | Initial direction | Initial physical level |
| --- | --- | --- |
| CAN_Ignition_Status | input | 1 |
| ACC_Sense | input | 1 |
| Safe_Shutdown | input | 0 |
| Reverse | input | 1 |
| Power Hold | output | 0 |
| Reset VIP | output | 1 |
| MAP_Normal_Mode | output | 0 |
| MAP_Powerdown_Ready | output | 0 |
| Emergency | output | 0 |
| DO_MIC_PWR_EN | output | 0 |
| DO_CAM_PWR_EN | output | 0 |
| DO_MAP_BOOT_FAIL | output | 0 |
| Mic Power Good | input | 0 |
| Camera Power Good | input | 0 |
| USB Power Good | input | 0 |
| DO_USB_PWR_EN | output | 0 |
| CAN Inhibit Sense | input | 0 |
| CAN_Day_Mode | input | 1 |

The additional VIM line defaults are lab assumptions, not captured vehicle state.
The bank is exported at base 224 to match original VIM's fixed GPIO path. See
[VIM startup](0011-vbs-vim-startup.md) for the custom command interface.

The firmware log confirms that the initial ignition and ACC levels are interpreted
as ON. Reverse is active-low and defaults to 1 (disengaged); the edge test restores
that value before starting services. Output writes are retained and observable. The module does not emulate a
CAN bus, VIP processor, or LVDS controller; `CAN_Ignition_Status` is the GPIO
interface exposed to applications, not a CAN-frame transport.

Input levels can be changed inside the guest through
`/sys/module/mazda_gpio/parameters/{ignition,acc,safe_shutdown,reverse}`. Values
are Boolean. Writes are rejected if the line has been configured as an output.
Use these only in the disposable lab guest. Original firmware files are unchanged.

## Build and verification

`just tools software` installs exact-version target headers and native build
helpers from the pinned Debian snapshot. ARM header archives are unpacked into a
staging directory and only their `/usr/src` contents are installed, preserving
the container's merged `/usr` links. The reference kernel volume remains read-only.

- `just dev software build_gpio`: compile the module independently of an active viewer.
- `just probe --verify-gpio --seconds 60 --debug-services --capture-sequence`: build and boot the overlay, test edge/value behavior,
  then check that the original system service reports STARTED.
- `just probe --probe-lvds --seconds 20 --debug-services`: diagnose the next display-service dependency with
  an actual VirtIO framebuffer. This is a diagnostic run, not a passing UI test.

The GPIO integration test passed on 2026-09-09. It checks rising and both-edge
poll notifications, module unload/reload, absence of notifications for unchanged values or filtered
falling edges, and readable output writes. The original `system_mazda_my14`
service now reports STARTED and MMUI's `ReportGuiAvailable` callback returns
success (100), where it previously returned 0 after the service exited.

This does not yet unblock the complete UI. The system service now waits for
display-state responses; LVDS requests time out. Thermal-zone reads also warn
because the generic board has no matching temperature sensor. In the first GPIO
run MMUI eventually failed its GUI health check. These failures remain visible;
no display-success replies or normal-mode events have been injected.

The bounded `just probe --probe-lvds --seconds 20 --debug-services` adds a real VirtIO framebuffer and traces the
original `lvds_service`. It opens `/dev/fb0`, but its vendor contrast ioctl
`0x40844628` returns `ENOTTY`. It also attempts the missing
`/sys/class/gpio/LVDS Mode Select` line and `/dev/ttymxc0` display UART. The probe
terminates it after five seconds. A display-control implementation therefore
needs either a software-backed service at the original D-Bus interface or an
emulation of the serial display protocol and vendor framebuffer controls.
The software display-control choice was approved and implemented; see
[software display control](0008-software-display-control.md) for current results.
The earlier timeout and GUI-health observations above describe the pre-display run.
The subsequent run traced an actual over-temperature event to the missing sensor.

The parked-state polarity check uses the native GUI listener’s queried
`Reverse Gear Status = 0` and rejects reverse-on events during startup. The
firmware does not emit a reverse-off transition when it initializes already off.
