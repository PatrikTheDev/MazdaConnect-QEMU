# Mazda Connect QEMU lab

Research workspace for running Mazda Connect firmware in QEMU. The current
reference package is CMU150 EU 74.00.324A.

This base provides repeatable Linux tooling, verified package storage, outer ZIP
extraction, a QEMU launch profile, and a read-only vehicle inventory script.
EU 74.00.324A has now been acquired and analyzed; its original BusyBox runs under
QEMU user-mode with its original libraries. A full-system QEMU guest now also boots
the Mazda rootfs using a pinned generic kernel. The software-rendering lab runs
the original intro, disclaimer, home menu and Settings screen over VNC, with
verified keyboard navigation. This currently requires llvmpipe and an explicit
[documented intro race fix](docs/findings/0016-intro-race-fix.md). It is not a
complete vehicle simulation; further service integration remains under
investigation. The optional queue fix below removes the observed websocket
exceptions in the verified startup and Settings navigation sequence. See [firmware findings](docs/findings/0002-eu-v74-analysis.md)
and [boot instructions](docs/guest.md).

## Start

Install Git, just, and a Docker runtime with Compose. No host Python, QEMU,
compiler, or privileged container is needed.

```sh
just doctor
just image-build
just test
just shell
```

With the verified firmware already analyzed in the lab volume, run
`just kernel-fetch`, `just firmware-resources`, `just resources-disk`,
`just guest-build`, and `just boot` to open the Mazda userspace shell in QEMU.
`just guest-test` performs a bounded boot/command/poweroff check.
`just firmware-resources` reconstructs and checks all 901 separate resource files.
`just resources-disk` builds their read-only ext4 disk; rebuild the guest afterward.
`just compositor` runs the original compositor headlessly with its IVI plugin.
`just compositor-test` verifies actual Wayland client communication.
The Vivante output path still requires an absent GPU device; see
[the crash diagnosis](docs/findings/0005-mounted-resources-compositor.md).

For the original UI through the software-rendering path, after preparing the
reference guest and resources:

```sh
just software-image
just software-prepare
just software-boot --renderer llvmpipe --intro-race-fix
```

In another terminal, run `just software-view` (VNC password: `mazda`). Use
`just software-key right`, `just software-key ret` and `just software-capture`
to navigate and capture the display. `just software-stop` stops the guest and
retains diagnostics. The firmware patch is opt-in and does not alter the
reference package. The separate Vivante work is not needed for this path.

`just test` checks package integrity handling, archive traversal rejection,
shell scripts, execution of a compiled ARM Linux probe through qemu-arm, and
full-system ARM QEMU initialization through QMP. It does not test a Linux boot.

The tooling image follows the host architecture. Its Debian base digest and APT
snapshot are pinned; `just versions` prints the installed package versions.
The included soft-float cross compiler is for lab probes. A Mazda-compatible
toolchain must be selected after examining the actual firmware ABI and libc.

## Firmware workflow

1. Copy `config/firmware/package.example.json` to a version-specific manifest.
2. Record the exact version, region, source, expected size and SHA-256. An
   observed local hash establishes identity, not independent authenticity;
   record how it was obtained in `provenance`.
3. Put a package in `artifacts/` and run:

```sh
just firmware-import config/firmware/YOUR-PACKAGE.json artifacts/YOUR-PACKAGE.up
just firmware-inspect config/firmware/YOUR-PACKAGE.json
just firmware-extract config/firmware/YOUR-PACKAGE.json
```

Alternatively, set an HTTPS URL and use `just firmware-fetch MANIFEST`.
The EU 74.00.324A manifest uses a public Yandex share and resolves a fresh download
URL on each fetch; the stored SHA-256 remains fixed. This is a community mirror,
not a Mazda-hosted distribution endpoint.
The example manifest intentionally cannot be imported or fetched until completed.
No unrelated regional image is selected automatically.

Files are stored at `/lab/firmware/ID/` in the Docker volume, with `original.up`,
its manifest, and an `outer/` extraction. Originals are write-protected and verified
again before inspection/extraction. Inspection exports JSON to `artifacts/`.
For an encrypted ZIP, provide `FIRMWARE_ZIP_PASSWORD` in your shell environment
before running the recipe; it is passed to the extractor, not stored in Git.

Extraction validates member paths and then uses native 7-Zip for efficient decryption.
It only handles ordinary outer ZIP files (including a trailing signature).
It rejects links, special files, duplicate paths and traversal. It does not execute
update instructions, decrypt arbitrary formats, verify Mazda signatures, or unpack
inner filesystem images. Directory ownership/timestamps are not reconstructed by
this outer-package step.

`just firmware-analyze config/firmware/cmu150-eu-74.00.324A.json` inventories
decompressed payload types and the rootfs tar metadata, checks regular-file vendor
MD5 records, and inspects selected ELF files with readelf. It also checks the package
signature against the bundled publisher key, which does not establish a trusted
Mazda certificate chain. Reports go to `artifacts/`; derived archives, instructions,
and numbered samples remain in the Linux volume. It does not build a runnable rootfs
or execute the vendor's updater.

`just firmware-probe config/firmware/cmu150-eu-74.00.324A.json` runs the original
BusyBox echo/help commands with its original loader, libc and libm. The minimal
library prefix is disposable and is not a reconstructed vehicle rootfs.

## Storage and changes

- Git: scripts, configuration, ordered patches, overlay files, and research notes.
- `artifacts/`: ignored input packages and exported reports/images.
- `runs/`: ignored logs and disposable guest state.
- Docker `lab-data` volume: Linux filesystems, extracted files and build caches.
- Ghidra: run the UI natively; keep databases outside Git and export useful scripts/notes.

The repository is mounted read-only in the container, except `artifacts/` and
`runs/`. Make source edits on the host. Do not use `docker compose down -v` unless
you intend to delete the lab data. Back it up before removing the Docker runtime.

See [layout and patch rules](docs/layout.md), [guest setup](docs/guest.md),
[vehicle collection](docs/vehicle.md), and [research sources](docs/sources.md).

The separately approved time-service deadline correction is also opt-in:
`just software-boot --renderer llvmpipe --intro-race-fix --time-deadline-fix`.
It enables the original time services and corrects their semaphore deadline's
clock domain. Both original time services now start, and the home screen displays
the guest time; the full boot and minute callback have been verified.
See [the time-service findings](docs/findings/0017-time-deadline-fix.md) for
scope, hashes and diagnostic recipes.

The approved [websocket queue correction](docs/findings/0018-websockets-queue-fix.md)
is enabled with `--websockets-queue-fix`. Test it in the original browser with
`just software-websockets-fix-test`. For original UI controls, use
`just software-key backspace` for Back and `just software-key m` / `n` for
clockwise / counterclockwise rotary input; Escape is not the UI Back control.

Use `just software-health-report /software/<retained-run>` to inspect observed
service states and frequent errors. The software launcher supplies the POSIX
shared-memory mount required by the original vehicle database; see
[validation and remaining issues](docs/findings/0019-posix-shared-memory.md).
