# Original VBS and VIM startup

The software service-manager configuration now starts original `jciVBS` with its
stock `settings` dependency. `just software-vbs-probe` captures its startup;
`just software-vim-probe` additionally runs a bounded syscall trace of original
`/jci/vim/vim_app`. These diagnostics deliberately do not assert UI readiness.

The system service's `VbsRadioProxy` binds the stock radio interface and calls
`VBS_RADIO_GetConnStatus`, subscribing through `VBS_RADIO_ConnectionStatus_enable`.
The radio module initializes inside VBS, but the CAN module logs failed VIM IPC
connections through `libjcivim_api.so` and `libjcipc.so`. VBS did not report its
service STARTED milestone in the bounded probe. Merely adding the process is
therefore not sufficient to provide vehicle or TAU readiness.

The original VIM daemon is normally started outside the service manager from
OPTStart. Its first probe failed creating input devices because `/dev/uinput`
was absent. The overlay now loads the matching upstream `uinput.ko`. A subsequent
probe successfully opened uinput and completed the keyboard/mouse creation ioctls.
Warnings about existing keyboard0/mouse0 aliases are retained; input routing
has not been redesigned or silently switched to VIM's devices.

VIM then fails `GPIOMON_init` while opening
`/sys/class/gpio/gpiochip224/vim`. This is a Mazda-specific GPIO interface, absent
from the generic kernel. Its contract must be recovered before emulation; an
ordinary empty file would not provide the expected behavior. Binary inspection
also identifies `/dev/cmu_io` and `/dev/spidev1.0`, although execution has not yet
reached those dependencies. Available symbols include `SPI_Init` (0x14008),
`SPI_Transfer` (0x142c8), `VIPBUS_init` (0xbf40), and `iuc_sendSPICommReady` (0xf318).

The approved approach preserves original VIM and emulates its underlying devices.
The GPIO module now exports the bank at base 224 and adds the write-only `vim`
attribute. `GPIOMON_ProcessEvent` supplies commands of the form `Reverse,1\n`.
Commands update the same GPIO state visible through named sysfs attributes;
input updates respect the configured IRQ edges. Output changes notify pollers,
matching VIM's read handler, which polls output values without input IRQ setup.
Malformed commands and names not observed in the handler are rejected.

Recovered command names are `Mic Power Good`, `Camera Power Good`, `USB Power
Good`, `Reverse`, `DO_USB_PWR_EN`, `CAN Inhibit Sense`, `CAN_Day_Mode`,
`Safe_Shutdown`, and `CAN_Ignition_Status`. The read handler monitors `Emergency`,
`Power Hold`, `DO_MIC_PWR_EN`, `DO_CAM_PWR_EN`, `MAP_Normal_Mode`,
`MAP_Powerdown_Ready`, and `DO_MAP_BOOT_FAIL`.

This does not yet provide SPI/VIP communication or TAU readiness.

Verification on 2026-09-09: `just software-gpio-test` passed command validation,
input IRQs, output poll notifications, module unload/reload, original system
startup, and the parked reverse-state check. `just test` passed all 13 unit tests,
shell checks, and ARM/QEMU smoke checks.

The subsequent `just software-vim-probe` opened `gpiochip224/vim` successfully.
The original GPIO read-handler thread started and read all seven monitored lines,
including Power Hold and Normal Mode at 1 as set by the original system service.
VIM then attempted `/dev/spidev1.0` ten times, each returning `ENOENT`. This is the
next concrete environment dependency, not a GPIO initialization failure. The
retained run is `/software/test-6l0841_p`; the recipe deliberately exits with its
usual diagnostic-only status rather than declaring the UI ready.

Further static inspection recovered `/dev/cmu_io` registration at 0x1154c:
ioctl `0x40084300` receives two 32-bit integers, the calling process ID and GPIO
42 (the original driver delivers SIGIO, signal 29). Its later role is VIP interrupt delivery. This call has not yet been reached
in the probe; the device and SPI/VIP protocol remain to be implemented. The pinned
kernel already enables `CONFIG_SPI=y` and `CONFIG_SPI_SPIDEV=y`.

The subsequent [SPI/interrupt transport](0012-vip-transport.md) resolves those
device initialization failures. Original VIM reaches IUC startup; VIP protocol
responses and TAU readiness are still outstanding.
