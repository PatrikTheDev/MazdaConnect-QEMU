# Mazda Connect QEMU lab

Run the original Mazda Connect intro, disclaimer, home menu, and Settings UI in
an ARM QEMU guest with software rendering and a live VNC display. This is an
experimental interoperability project for **CMU150 EU 74.00.324A**, not a complete
vehicle simulator or a firmware flashing tool.

The repository contains source, integration scripts, configuration, and research
notes. **Bring your own firmware.** Firmware packages, vendor binaries, UI assets,
and generated guest images are not distributed here.

## Requirements

- Git, Bash, [just](https://just.systems/), and Docker with Compose v2 using Linux containers.
  Bash is standard on macOS/Linux; use a WSL2 shell for Windows experiments.
- A VNC client. macOS Screen Sharing works with `just view`; on other systems,
  connect a client manually to `127.0.0.1:5901`.
- The exact `cmu150_EU_74.00.324A_update.up` package and its ZIP password, obtained
  independently with permission to use them. The archive password is documented in
  [published research](https://kyprizel.net/work/mazda-cmu-fun.pdf), slide 22; it
  is not a vehicle login credential.
- Plan for at least 30 GiB free in Docker storage and 8 GiB RAM allocated to Docker.
  These are practical starting budgets, not measured minimum requirements. Kernel
  compilation uses four workers; the running guest uses 1.5 GiB RAM.

The software UI has been exercised on Apple Silicon macOS with a Linux ARM64
Docker runtime. The CI configuration targets Linux AMD64 tooling; the full
UI on other hosts remains unverified. Host QEMU, Python, cross-compilers, GPU
passthrough, KVM, and privileged containers are not required. The guest uses TCG;
expect slower startup and animation than a real vehicle.

## First setup

Clone this repository and enter its directory. Place your firmware package
**directly in `artifacts/`**. Setup checks it against the supported manifest:

| Property | Required value |
| --- | --- |
| Region / version | EU / 74.00.324A |
| Size | 2,432,208,800 bytes |
| SHA-256 | `3a506745c4ae65c21e0427714f377a4765b92e339cdbd6bf1b91ec398bb1a963` |

The hash identifies the research input. Community checksum corroboration does
not establish a trusted Mazda signing chain. Other versions or regions need ABI
and patch validation; changing a manifest alone does not add support.

Provide the password through your shell environment, or create an ignored `.env`
file at the repository root containing `FIRMWARE_ZIP_PASSWORD=...`. Do not commit
that file or paste the password into issue reports.

```sh
just doctor
just setup artifacts/cmu150_EU_74.00.324A_update.up
just start
```

`setup` builds the pinned tooling images, verifies and imports your package,
extracts and analyzes it, reconstructs the resources disk and reference guest,
prepares the software runtime, compiles the 2 GiB userspace kernel and matching
modules, and builds the UI guest. A fresh four-worker setup took about 50 minutes
on the validation host. `just setup artifacts/PACKAGE.up --jobs 8` can use more
compile workers when your Docker runtime has enough CPU and memory. No rooted
vehicle is needed. Setup never downloads Mazda firmware or runs its updater.
Repeated setup verifies the input and reuses an existing atomic outer extraction;
it does not remove lab data.

In another terminal:

```sh
just view
```

The VNC password is **`mazda`**, a public lab password. The endpoint binds only to
host loopback. Use the arrow keys and Enter, Backspace for Back, and `m` / `n` for
clockwise / counterclockwise rotary input. For scripted interaction:

```sh
just key right
just key ret
just capture
just status
just stop
```

Ctrl-C in the boot terminal also shuts down the guest and retains logs. Restart
without compiling with `just restart`. Run `just build` after changing build inputs
or tooling; `just start` rebuilds the guest overlay before booting.

## What the default UI configuration changes

`just start` and `just restart` explicitly select the built `vmsplit2g` kernel,
Mesa llvmpipe, and three documented firmware corrections:

- [Intro completion race](docs/findings/0016-intro-race-fix.md).
- [Time-service deadline clock](docs/findings/0017-time-deadline-fix.md).
- [WebSocket transition queue](docs/findings/0018-websockets-queue-fix.md).

These corrections are applied to separate generated outputs; the reference
package remains unchanged. The lower-level research runner keeps them opt-in.
The [kernel configuration](docs/findings/0027-two-gib-kernel-profile.md) matches
original VBS pointer expectations. Source and dependency hashes are pinned;
fresh kernel builds may differ because private signing keys are generated locally.

The lab supplies GPIO and VIP/SPI devices for original VIM, a configurable thermal
sensor, a software display-control service, an intro-video player, and an HDA audio
adapter. Original Mazda libraries and Opera render the UI through the software
compositor adapter. Examples:

```sh
just start --temperature 30000 --trip-temperature 95000
just start --microphone-tone 700 --record-audio
```

Temperature values are millidegrees Celsius. Microphone input defaults to silence;
there is no host microphone capture. HDA capture gain has a documented lab mapping,
not the original vehicle codec calibration.

Home and Settings navigation have been verified. Some animation watchdog timeouts
remain, and VIP application responses and vehicle state coverage are incomplete.
Navigation, radio reception, Bluetooth device integration, and complete vehicle
behavior are not validated. Vivante GPU emulation is separate research and is not
required for this software path. See the [latest rendering evidence](docs/findings/0029-winston-fixed-point-coordinates.md).

## Tests and research

Firmware-free checks, suitable for public CI:

```sh
just tools reference
just test
```

These run unit tests for integrity/archive handling and orchestration, shell
checks, a working-tree and history publication guard, and ARM userspace/QEMU initialization
smoke checks. They do not claim the Mazda UI boots.

After setup, `just verify` checks real compositor pixels and translation
coordinates. `just report /software/RETAINED-RUN` summarizes observed service
states and errors. Use `just probe` for bounded browser experiments and
`just dev SCOPE SCRIPT` for specialized analysis. Diagnostic runs can deliberately
exit nonzero to require inspection; see [research commands](docs/research.md).
`just --list` lists the small public command surface.

## Storage and publication

| Location | Contents | Public? |
| --- | --- | --- |
| Git | Source, scripts, configuration, patch procedures, sanitized notes | Yes |
| `artifacts/`, `runs/` | Input packages, exported reports, images and logs | No; ignored |
| `mazda-qemu_lab-data` Docker volume | Imported firmware, resources and reference guest | No |
| `mazda-qemu-software_software-data` Docker volume | Extracted userspace, kernels, builds and retained runs | No |

The repository mounts read-only in containers, except `artifacts/` and `runs/`.
Guest rootfs changes live in RAM; diagnostics persist in the private volumes.
Do not use `docker compose down -v` unless you intend to delete lab data.

Publish source-only releases. Do not upload firmware, generated initramfs files,
resource/runtime disks, vendor libraries, exported volumes, or full modified Mazda
applications through Git, Git LFS, Actions artifacts, or release attachments.
The publication guard is a useful check, not an exhaustive secret/provenance audit.
See [release procedure](docs/release.md), [fresh-volume validation](docs/findings/0030-source-release-validation.md),
[third-party inputs](THIRD_PARTY.md),
[contributing](CONTRIBUTING.md), and [layout](docs/layout.md).

Original project code and documentation are **GPL-2.0-only**; see [LICENSE](LICENSE).
External components retain their own licenses. This independent project is not
endorsed by Mazda.
