# Mounted resources and compositor crash diagnosis

Reference firmware: CMU150 EU 74.00.324A. Lab: QEMU virt-7.2, Cortex-A15,
Debian 6.1.0-50-armmp kernel, original Mazda BusyBox and glibc 2.11.1.

## Resources

`just resources-disk` verifies the reconstructed resource archive hash and creates
a 3 GiB ext4 filesystem using `mkfs.ext4 -d`, without mounting it on the host.
The filesystem passes `e2fsck -fn`. QEMU opens it read-only; lab init mounts it
`ro,noload` at `/tmp/mnt/resources`, reached through the vendor's `/mnt` and
`/resources` symlinks. Discovery uses the `MAZDA_RESOURCES` filesystem label.

The guest loads matching virtio-mmio, virtio-blk, ext4 and dependency modules.
The CRC32C soft dependency is explicitly satisfied by `crc32c_generic`:
Debian's alias also selects ARMv8 CRC acceleration, which cannot load on the
emulated Cortex-A15. Creating `/tmp/mnt` is also necessary before following the
vendor's `/mnt` symlink. These were lab setup defects and are now fixed.

The mounted sample `/resources/vui/emnavi/poi_dictionary_mnc.txt` matches MD5
`2bf180f82ac4851fd0e608dbc19cb619`. This expected MD5 is calculated from the
SHA-256-verified source sample because the original BusyBox has no SHA-256 applet.
All 901 source files were CRC32-verified during resource reconstruction. The
guest check samples mounted content; it does not rehash every mounted file.

## Crash evidence

`just guest-graphics-probe` starts the original compositor with
`WL_COMPOSITOR_CONFIG=/etc/wayland/compositor_jci_display.conf`, original
libraries, and a writable private `XDG_RUNTIME_DIR`. A statically linked ARM
ptrace helper records main-thread open/access/ioctl results and forwards signals
without replacing syscall results. A separate disposable ext4 disk holds cores.

The relevant syscall sequence is:

```text
open /usr/lib/libwlxs-viv-output.so -> success
open /usr/lib/libGAL.so -> success
open /dev/galcore -> -ENOENT
open /dev/graphics/galcore -> -ENOENT
open /dev/galcore -> -ENOENT
open /dev/graphics/galcore -> -ENOENT
SIGSEGV, r3 = 0
```

GDB locates the fault in `libGAL-wl.so`, reached through `libGAL.so`:

```text
gcoHAL_QuerySeparated3D2D+44:
    ldr r5, [r3, #228]
```

This is a null internal-pointer dereference after the missing GPU-device opens.
The evidence identifies an unmet Vivante device expectation and an unchecked
initialization failure in the binary. It does not indicate an ARM instruction
emulation failure. Missing filtered input nodes also generate retries, but are
not the faulting instruction. We have not proved that providing a galcore node
alone would suffice: working ioctls, memory mappings, GPU semantics and framebuffer
behavior would still be required. No fake success-returning device was added.

GDB resolves exported function names and the faulting instruction, but emits an
executable/core matching warning and lacks a matching thread-debug helper. The
full caller unwind is incomplete. The executable comes from the hash-verified
rootfs, and its hash is recorded with the core. Treat the raw register/instruction
evidence as established; do not treat the partial backtrace as a complete call tree.

## Working headless compositor

The same original executable stays running with the lab configuration
`plugin = ivi`. No vendor binary or library is patched. A static ARM Wayland
client connects, requests the registry, and completes a `wl_display.sync`
round trip. It observes:

```text
wl_display, wl_compositor, wl_subcompositor, wl_shell, wl_shm,
wl_ivi_shell, wl_ivi
WAYLAND_ROUNDTRIP_OK outputs=0
```

The probe follows the documented [Wayland wire protocol](https://wayland.freedesktop.org/docs/book/Protocol.html).
The compositor also exits cleanly on SIGTERM. This verifies a functioning
protocol/event loop and original IVI plugin in the emulated environment, with
zero display outputs. It does not render pixels or start Opera.

Use `just compositor` for an interactive guest with this mode running, or
`just compositor-test` for a bounded boot/resource/Wayland/poweroff check.

## Evidence and independent experiments

- `runs/eu-v74-graphics-probe.log`: vendor syscall trace and headless protocol result.
- `runs/eu-v74-compositor-gdb.log`: core analysis.
- `runs/eu-v74-compositor-boot.log`: automatic headless startup verification.
- `artifacts/cmu150-eu-74.00.324A.graphics-debug.json`: retained core, diagnostic
  disk and analysis sysroot locations, plus hashes.
- `artifacts/cmu150-eu-74.00.324A.resources-disk.json`: disk/archive hashes.

These generated files stay outside Git. `just test` passes 13 tests, ShellCheck,
ARM user-mode execution and QEMU initialization; `just compositor-test` passes
the full-system checks described above.

The next two research paths are a software output plugin for the original
compositor and faithful Vivante device support. Develop them in separate
worktrees, with separate Docker project/image names, writable volumes, profiles,
guest images and logs. The default Compose project is named `mazda-qemu` and its
data volume is shared by checkouts unless deliberately overridden. A worktree
alone does not isolate Docker state. Share reference firmware read-only, and
do not overwrite the base guest or run two instances against a writable disk.
Neither backend implementation is included in this checkpoint.
