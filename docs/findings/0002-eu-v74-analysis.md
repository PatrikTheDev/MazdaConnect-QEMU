# EU 74.00.324A acquisition and analysis

Date: 2026-09-09. Reference research package: CMU150 EU 74.00.324A.

## Acquisition and integrity

Package: `cmu150_EU_74.00.324A_update.up`, 2,432,208,800 bytes.

SHA-256: `3a506745c4ae65c21e0427714f377a4765b92e339cdbd6bf1b91ec398bb1a963`.

Downloaded from the [public Yandex share](https://disk.yandex.ru/d/QIjY9lRX3NugBA)
linked in a [first-hand MazdaKlan checksum report](https://www.mazdaklan.cz/threads/aktualizace-systemu-mzd-connect-s-dotykovym-displejem-2014-2018.54/page-23).
The downloaded bytes match the reported SHA-256 and size. Community checksum
corroboration is not proof of a trusted vendor distribution chain.

The last 256 bytes verify as an RSA/SHA-256 signature over the preceding bytes,
using `publisher_cert.pem` from inside the archive. OpenSSL reports `Verified OK`.
This verifies consistency with the bundled key; we have not validated a trusted
Mazda certificate chain. The bundled publisher certificate has 2013–2016 validity
dates, so the signature result must not be described as present-day PKI validation.

Extraction used the archive password published in [this research post](https://www.fabidouille.com/?p=151).
It can be supplied via `FIRMWARE_ZIP_PASSWORD`; no vehicle credentials were used.

## Package structure

- 982 outer ZIP entries, of which 903 are under `resources/` (including directory
  and instruction entries).
- `versions.ini.gz` reports display version `74.00.324`.
- Main instructions declare 21 stages, 1,127 total steps, and package type Reinstall/Mass.
- Kernel, rootfs, recovery, boot components, GNSS, resources and other update stages
  are present. No update script was executed.
- `fail-safe/binary.ini.gz` describes a 7 MiB recovery partition at `/dev/mtd6` on
  NOR. Both normal and extended update sequences include this stage. This package
  does update recovery; a single `.up` must not be assumed to omit recovery.

## Root filesystem

`rootfs1upd/execute.ini.gz` maps `e0000000001.dat` to `rootfs.tar.gz`. The outer
`.dat.gz` therefore has another gzip/tar payload after its first decompression.

The rootfs tar contains 10,121 entries and 428,574,218 bytes of regular-file content.
All 8,464 paths in the bundled rootfs MD5 list were checked and matched, with zero
missing paths. These checks supplement the full-package SHA-256.

The updater targets `/dev/ffx01p1` with `mkfs.relfs` and a `relfs` mount. We can
recover files from the tar without interpreting an on-device relfs image. The
original tar preserves numeric ownership, modes, links and other metadata; the
analyzer inventories these rather than materializing a complete filesystem.

`/resources` is populated separately through `resources/files.ini.gz`, which
declares 1,020 instructions. It includes voice/navigation/media resources and
certificates. A rootfs-only extraction does not reconstruct the installed system.

## Executables and graphics

- Sampled binaries: 32-bit little-endian ARM, EABI5, ARMv7 attributes.
- Original loader: `/lib/ld-linux.so.3`; glibc: 2.11.1. Preserve this legacy ABI/sysroot
  when compiling compatible helpers; do not substitute an armhf userspace.
- BusyBox: v1.19.2, build string `2020-02-14 18:04:06 JST`.
- Opera: `/jci/opera/opera`, not stripped. Some plugins retain debug information.
- Opera directly needs EGL, GLESv2, Wayland EGL/IVI libraries, and JCI libraries.
- Graphics stack includes `libEGL-wl.so`, `libGAL-wl.so`, Wayland/Vivante libraries,
  and `lib/modules/3.0.35/kernel/drivers/mxc/gpu-viv/galcore.ko`.
- `jci/sm/sm.conf` launches Opera with `-u /jci/gui/index.html`; its declared service
  dependencies are `jciAppsdk` and `jciDbapi`. The manager also declares a watchdog
  and board-reset behavior. Additional runtime dependencies require tracing.

The decoded primary kernel payload starts with `TOOB`, rather than a directly
identified zImage/uImage header. It includes a Linux 3.0.35 version marker.
The image wrapper and embedded boot filesystem still need investigation. The
rootfs tar does not contain the usual `/etc/inittab`, `/etc/fstab` or `/etc/init.d/rcS`.
Do not invent a stock init sequence from the tar alone.

## Execution result

`just firmware-probe config/firmware/cmu150-eu-74.00.324A.json` successfully executed
the original BusyBox echo and help commands through qemu-arm. It used only the
original BusyBox, loader, libc, libm and their original library symlinks in a
disposable directory. No binary patches or host-library substitutions were needed.

This proves a first Mazda executable runs under userspace emulation. It does not
prove original-kernel boot, service startup, graphics compatibility or UI rendering.

## Reproduce and inspect

Use the manifest in `config/firmware/cmu150-eu-74.00.324A.json` with the `just`
firmware-fetch/import, firmware-inspect, firmware-extract, firmware-analyze and
firmware-probe recipes. Supply the published ZIP password for extraction.

Host artifacts:

- `artifacts/cmu150_EU_74.00.324A_update.up`: downloaded package.
- `artifacts/cmu150-eu-74.00.324A.inventory.json`: outer members.
- `artifacts/cmu150-eu-74.00.324A.analysis.json`: signature, payload, tar, ELF and service facts.
- `artifacts/cmu150-eu-74.00.324A.probe.json`: BusyBox execution evidence.

Linux volume: `/lab/firmware/cmu150-eu-74.00.324A/` contains the verified original,
outer extraction and `analysis/` with the rootfs tar, decoded instructions, kernel
payload and numbered samples. The sample-to-original-path map is in the JSON report.

Next: decode the boot image and determine the actual init sequence, then assemble
a metadata-preserving derived filesystem with resource mappings. Investigate the
graphics boundary before choosing any compatibility implementation. No hardware
service has been replaced or patched.
