# Original compositor with CPU output

The experimental software path uses `compose.software.yaml`, a separate Docker
project and writable `/software` volume. The reference firmware and guest volume
is mounted read-only at `/lab`. It does not depend on the separate Vivante work.

## Verified milestone

`just software-test` boots the original rootfs with the mounted resource disk,
loads the original Winston compositor and IVI plugin, and adds the lab CPU output
plugin. A real Wayland client submits an 800×480 XRGB8888 shared-memory buffer.
The test checks every output pixel against four color bars and requires a frame
callback and clean guest shutdown. This passed on 2026-09-09.

The plugin uses the vendor compositor's scene traversal and coordinate transforms.
It implements buffer allocation, shared-memory uploads, alpha blending, output
announcements, damage scheduling, and frame completion. Captured frames are PPM
files. This proves the software output path, not the complete Mazda UI.

## Recovered ABI

The ABI is specific to Winston `0.13.5 141205` in CMU150 EU 74.00.324A:

- Winston SHA-256: `43d86d994ae178569bef0324f9f9f25fe238b5d06f19a6114e80ab5b7d7ed2e5`
- Opera SHA-256: `0807ab186b322f6b1c3f745ca0d438e838d40fa0fc068dfc0f5aa5cc2202b724`
- ARM EABI soft-float calling convention; 32-bit pointers.
- Plugin base: 20 bytes; output: 48 bytes; buffer base: 24 bytes.
- Output operation table: 84 bytes. See `src/software/winston-abi.h`.
- The draw callback receives output, view, subview offsets, and surface.
- Surface offset 52 holds the buffer; view offset 240 holds opacity (0–255).

The minimal plugin is linked without a new libc dependency and resolves symbols
against the original compositor process. Non-shared-memory imports are rejected;
the plugin does not pretend to implement Vivante buffer objects.

## Browser integration in progress

Opera's `--noHWAccel` selects CPU painting, but its launcher still initializes
EGL. The current default uses Opera's GLES painter backed by Mesa softpipe;
`--no-hw-accel` selects CPU painting for comparison. A private Debian ARMEL runtime
supplies Mesa software EGL/GLES to Opera, invoked explicitly with its own loader
and library path. Original system libraries are not replaced. Dependencies come
from the same pinned Debian snapshot as the lab image. Mesa is mounted from its
own read-only ext4 disk to avoid initramfs memory exhaustion.

A controlled HTML page has rendered successfully in the original Opera binary
through the GLES/softpipe path. The separate `--inspect-surface` diagnostic uses
the vendor `ivi-shell` utility to show the otherwise hidden browser surface.
This diagnostic is not part of normal Mazda UI startup.

The guest now restores the firmware-supplied backup account database into
`/config-mfg/passwd`, creates the expected writable `/var` and `/data` targets,
starts both original D-Bus buses, and provides real VirtIO input devices. Modern
VirtIO MMIO transport is required for those input devices. Device aliases provide
the `/dev/input/keyboard0` name hard-coded by the MMUI diagnostic component.

The lab service-manager configuration starts the original settings, BLMSettings,
AppSDK, DBAPI and MMUI services. All five have reported `SM_SVC_CMD_STARTED`.
The GUI exchanges `Global.GetStartupSettings` and `Global.InitGui` with MMUI.
Hardware-dependent services remain unavailable, and the interactive UI still
stays in `system.IntroAnimation` after video playback. The vendor WebSocket JavaScript also reports `_isStack` is
not a function; its helper is declared globally but called as an instance method.
No firmware JavaScript has been patched.

`just software-opera-test` currently captures a bounded diagnostic run and exits
nonzero to avoid claiming successful UI startup. Supporting
services, browser startup, rendering correctness, and interactive output remain
under investigation.

Use `just software-opera-test --test-page --inspect-surface` for the controlled
browser page, or omit `--test-page` to exercise the Mazda GUI. The separate visible
capture is `artifacts/software-visible.ppm`; `software-buffer.ppm` records uploaded
buffer RGB independently of compositor visibility and alpha.

## Software intro player

The vendor `/usr/bin/splashplayer` fails after opening the absent `/dev/mxc_vpu`.
The authorized software replacement decodes the original 800×480 VP8 IVF files
with libvpx and submits XRGB shared-memory buffers to the original compositor.
It implements the observed `-q`, `-l`, `-p`, `-t`, and `-z` arguments, registers
the original IVI surface name, writes the ready PID file after the first frame
callback, and exits normally after a `-q` movie. Looping and hold-last-frame modes
are implemented but have not yet received equivalent integration coverage.

Only the disposable guest overlays `/usr/bin/splashplayer`; the original is kept
at `/lab-software/splashplayer-vendor` for comparison. The reference firmware is
unchanged. The static decoder comes from the pinned ARMEL package snapshot.

Captured compositor frames visibly show the original `TranLogo.ivf` animation.
All 120 source frames decode. Presentation drops overdue frames under TCG: recent
runs presented 36–49 frames and took roughly 15–28 seconds for the five-second
movie. Playback is functional, but it is not yet real-time.

Debug logs prove the original service manager delivers both STARTED and STOPPED
events to MMUI. `UIA_SYSTEM_OnFinishIntroAnimation` executes and reports that the
intro is finished. Absence of these messages at Info level was a logging filter,
not a failed subscription.

`just software-video-test` requires complete decoding, multiple distinct visible
compositor captures, MMUI completion, and clean guest shutdown. It tests the video
milestone only. `--capture-sequence` records frames every five seconds;
`--debug-services` enables the firmware's supported Debug logging in the guest.
Compositor frame files are published by atomic rename so readers cannot capture
a partially written frame.

## Remaining system-mode blocker

After video completion, MMUI calls `UIA_SYSTEM_SYSTEM_sendHMIReady` and waits for
BLM_SYSTEM to transition to normal mode. The lab now attempts the original
`system_mazda_my14` service with the stock arguments and board reset disabled.
It connects to D-Bus, but its hardware-signal module fails to initialize:

- `/sys/class/gpio/Power Hold/value` is absent (fatal to initialization).
- `/sys/class/gpio/CAN_Ignition_Status/{direction,edge,value}` is absent.
- `/sys/class/gpio/MAP_Normal_Mode/value` is absent.

The service exits before STARTED. MMUI remains responsive, including GUI health
checks, but remains in IntroAnimation. This is an unmet vehicle-platform
expectation, separate from GPU/VPU emulation and the working software renderer.
No GPIO files, hardware-success stubs, or normal-mode events have been fabricated.
The approved next step is a behavioral GPIO simulation that preserves the
original system service. That module is separate from the viewer milestone.

## Continuous VNC viewer

Run `just software-boot` to build and start the original UI services. In another
terminal, run `just software-view` to open macOS Screen Sharing at
`vnc://127.0.0.1:5901`. QEMU starts its VNC server before guest startup; the default
five-second service delay allows time to connect. Use `--start-delay 20` if needed.

The CPU compositor writes each completed frame to the guest's 800×480 XRGB8888
VirtIO framebuffer. QEMU's native VNC server streams that scanout continuously.
The framebuffer is put into graphics mode to prevent the kernel console cursor
from overwriting UI pixels. This uses the generic VirtIO display, with Mesa still
forced to softpipe; it does not use the Vivante work. VNC is published only on the
host's loopback interface. Enter the development password `mazda` in macOS
Screen Sharing. Password authentication is enabled for compatibility with that
client; this public lab credential is not intended for remote exposure.

Useful recipes:

- `just software-run`: restart the existing build without rebuilding.
- `just software-stop`: cleanly shut down the foreground guest from another terminal.
- `just software-status`: inspect the QEMU state and connected VNC clients.
- `just software-capture`: save the current scanout as `artifacts/software-live.png`.
- `just software-boot --test-page`: show the controlled browser page.
- `just software-boot --seconds 65 --start-delay 0`: bounded original-UI startup.
- `just software-vnc-test`: verify RFB updates, desktop size, exact colors and text.

Ctrl-C also shuts down the guest. Live logs are saved under `runs/software-live*`
and the diagnostic disk is retained in `/software/live-*`. Service startup is
shared with automated tests in `overlays/software/start-services`. Builds and
runs acquire one lock for the software volume, preventing simultaneous mutation
of a guest's mounted runtime disk. Stop a running software guest before testing
or rebuilding. The separate Vivante volume/worktree is unaffected.

The VNC integration test passed with 44 updates and exact 800×480 browser pixels.
VNC availability does not mean that the vehicle-dependent system-mode blocker
above is solved: the original animation plays, then the GUI still waits for the
vehicle-state dependencies. GPIO and software display-control support have since
been added; see [current display-control findings](0008-software-display-control.md).

## Commands and artifacts

Run `just software-image`, `just software-prepare`, then `just software-test`.
The reference firmware, kernel, resources disk and guest must already exist.
`just software-opera-test` adds the private runtime for browser experiments.

Logs are written to `runs/software-test.log`; frames to
`artifacts/software-pattern.ppm` or `artifacts/software-opera.ppm`. Each run retains
its diagnostic disk and any cores in `/software/test-*`. These generated files
are excluded from Git.
