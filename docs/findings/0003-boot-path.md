# Boot image and first full-system guest

Date: 2026-09-09. Firmware: EU 74.00.324A, package SHA-256 in the firmware manifest.

## TOOB layout

The observed 3,985,408-byte image starts with `TOOB` and a little-endian entry
count of 3 at offset 4. A table starts at 0x40. Each observed 20-byte record holds
five little-endian uint32 values: component type, record size, byte length,
starting 512-byte sector, and allocated sector count. Component meanings below
are inferred from their validated contents, not an official format specification.

| Type | Offset | Byte length | Contents |
| --- | --- | --- | --- |
| 0 | 0x200 | 2,404,776 | ARM zImage; magic at component offset 0x24 |
| 2 | 0x24b400 | 125 | NUL-terminated kernel command line |
| 1 | 0x24b600 | 1,579,252 | gzip-compressed newc initramfs |

The kernel command line selects `ttymxc1,115200` and includes i.MX-specific
display/VPU settings. The decoded initramfs has 55 entries, including a native
ARM `/init`, glibc, Datalight flash/relfs modules and JCI modules. It contains no
shell-based rcS sequence.

The decoder validates record bounds, allocated sector counts, overlap, component
signatures and newc structure. It saves original components without modifying them.
The decoder intentionally supports this observed layout, rather than guessing at
unknown future TOOB variants.

## Original startup chain

The small initramfs `/init` imports mount, init_module, chroot and exec functions.
Its data and disassembly identify proc/sys/dev mounting, Mazda/JCI and Datalight
module loading, `/dev/ffx01p1` mounted as relfs at `/newroot`, and the handoff to
`/sbin/init` after chroot. It also contains early display/camera startup paths.

Rootfs links resolve `/sbin/init` → `init_target` → `init_cmu`. `init_cmu` is an
unstripped native ARM executable with named startup actions, including GPU/module
loading, data/config mounts, DBus, native GUI control and
`/usr/bin/wayland-viv-compositor`. We have statically identified these actions,
not proven their entire runtime ordering or replayed original-board startup.

This makes direct reuse of the original init on virt inappropriate: it depends on
real JCI devices, original-kernel modules, Datalight flash storage, and Vivante
graphics. No shims returning invented device state have been added.

## Lab boot result

A pinned Debian 6.1.0-50-armmp kernel boots the original Mazda rootfs tar converted
to newc on QEMU virt-7.2 with Cortex-A15 and TCG. All 10,121 vendor entries are
included, retaining file contents, ownership, modes, timestamps and symlinks.
Two lab-only entries are added: `/lab-init` and `/dev/console`.

The lab entry point starts a serial shell using the original Mazda BusyBox and
glibc. The original init files are untouched and not executed. Separate resource
payloads and state partitions are not reconstructed yet.

Validation: `just test` passed nine tests, ShellCheck and the tooling/QEMU smoke
tests. `just guest-test` reached `MAZDA_LAB_READY`, executed a BusyBox output check,
reported kernel `6.1.0-50-armmp`, and powered off cleanly. This establishes a
full-system userspace shell, not a boot of the original Mazda kernel or UI.

Evidence: `artifacts/cmu150-eu-74.00.324A.boot.json`,
`artifacts/cmu150-eu-74.00.324A.guest.json`, and `runs/eu-v74-boot.log`.

Next: reconstruct the separate resource mappings and identify the smallest service
set needed for the browser. The original graphics ABI remains an unresolved
boundary; changing the lab kernel does not solve it.
