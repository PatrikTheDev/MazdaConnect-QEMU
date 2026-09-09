# Boot the Mazda userspace lab

After importing, extracting and analyzing EU 74.00.324A:

```sh
just kernel-fetch
just firmware-resources
just resources-disk
just guest-build
just guest-test
just boot
```

The default `eu-v74-lab.json` profile uses QEMU virt-7.2, Cortex-A15, TCG and
1.5 GiB of guest RAM. It boots Debian's pinned 6.1.0-50-armmp kernel with the
10,121-entry Mazda rootfs tar converted to an initramfs. The kernel package is
hash-verified and unpacked without running its installation scripts. Its armhf
packaging does not replace Mazda's userspace libraries.

The builder preserves regular-file content, numeric UID/GID, mode, mtime and
symlink targets. Unsupported tar types/PAX metadata and writes through symlinks
are rejected. No filesystem tree is extracted onto the host to make this image;
tar members are serialized directly into newc. Absolute symlinks resolve inside
the guest. Build evidence is exported to `artifacts/cmu150-eu-74.00.324A.guest.json`.

`/lab-init`, `/dev/console`, and `/lab-modules/` are added. The latter contains
matching generic kernel disk/filesystem modules, static diagnostic tools, and
the headless compositor launcher/configuration. Original Mazda init programs and
libraries remain present and unchanged. The lab entry point mounts proc/sys/dev,
then opens an interactive shell with the original BusyBox. It does not start
vehicle services, load the incompatible 3.0.35 modules, or provide missing Mazda
hardware. `/resources -> /mnt/resources -> /tmp/mnt/resources` resolves to a
3 GiB ext4 disk mounted `ro,noload`. QEMU also opens the disk read-only. Mounts
use filesystem labels, so adding a diagnostic disk cannot swap their roles.
The disk is built without host mounts or container privileges from the verified
resource archive. Matching virtio-mmio, virtio-blk, ext4 and dependency modules
are loaded; CRC32C uses its generic implementation for Cortex-A15.
This is not a complete restored CMU.

The guest lives in RAM; changes disappear at shutdown. To shut down:

```sh
/bin/busybox poweroff -f
```

`just guest-test` verifies kernel boot, the lab readiness marker, an original
BusyBox command, a mounted resource sample's content, and guest poweroff. Its
serial log is `runs/eu-v74-boot.log`. The sample is SHA-256-verified on the host;
the original BusyBox checks its derived MD5 because it has no SHA-256 applet.
`just test` checks tooling and archive handling without requiring downloaded firmware.

## Debugging and graphics

`just guest-graphics-probe` boots the lab guest, sets `WL_COMPOSITOR_CONFIG` to
the vendor display configuration, and captures help, a main-thread syscall trace,
and a core dump. It then verifies the original compositor using a lab headless
configuration. The serial transcript is `runs/eu-v74-graphics-probe.log`, with
offline GDB results in `runs/eu-v74-compositor-gdb.log`. The diagnostic disk and
symbol prefix remain in the volume; their locations and hashes are exported in
`artifacts/cmu150-eu-74.00.324A.graphics-debug.json`.

`just compositor` boots with the original compositor and IVI plugin running
headlessly. It opens `/tmp/lab-wayland/wayland-0`; logs go to
`/tmp/lab-compositor.log`. `just compositor-test` checks registry discovery and a
Wayland sync callback in this mode, then powers off. To verify it manually in
the guest:

```sh
/lab-modules/wayland-check /tmp/lab-wayland/wayland-0
```

The headless mode advertises the original IVI interfaces but has zero outputs;
it does not render the Mazda UI. The vendor Vivante path still fails because
its GPU device is absent. See [the diagnosis](findings/0005-mounted-resources-compositor.md).

`just debug` pauses at startup and exposes GDB on host localhost:1234. Use matching
kernel symbols when debugging kernel code; the regular Debian image package does
not supply a full unstripped vmlinux. Debug symbols are a separate future dependency.

Set `graphics` to true in a new profile to add virtio GPU, USB input and VNC.
The guest also needs compatible drivers and a graphics stack. The default shell
profile has no graphical display; enabling VNC alone cannot make Mazda's original
Vivante stack work. QEMU display initialization has not been validated for this image.

Guest networking is disabled. Compose publishes VNC/GDB only on host loopback.
Two simultaneous runs with service ports need different host port mappings.
`config/qemu/virt.json` remains an explicit template for custom kernels/initramfs.

## Original boot path

```sh
just firmware-boot-inspect config/firmware/cmu150-eu-74.00.324A.json
```

The decoder saves the original zImage, command line, compressed initramfs, native
init binaries and disassembly under `/lab/firmware/cmu150-eu-74.00.324A/boot`.
It does not execute the original init programs. See the [boot findings](findings/0003-boot-path.md)
for their hardware requirements and the distinction between original and lab boot paths.
