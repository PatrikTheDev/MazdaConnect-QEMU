# Resources and first compositor execution

Analysis of reference package EU 74.00.324A on 2026-09-09. This records the first
probe; subsequent mounting and crash diagnosis are in finding 0005.

## Resource archive

`just firmware-resources` reconstructs `/resources` from the update's
`resources/files.ini.gz`, decoding each referenced gzip payload once. All 901
files match their instruction's CRC32. Together they contain 2,529,973,599 bytes;
the instructions also create 117 directories. Output is
`/lab/firmware/cmu150-eu-74.00.324A/analysis/resources.tar` in the Docker volume.
The host report `artifacts/cmu150-eu-74.00.324A.resources.json` records each file's
destination, mode, size, CRC32 and SHA-256, plus the resulting archive SHA-256.

The parser accepts Create and Copy, recognizes the initial informational echo
and clean-directory instruction without executing either, and rejects other
commands, unsafe paths, duplicates and file/directory conflicts. Payloads stream
through a temporary file to bound memory use. No vendor script runs. The tar is
published after all file CRCs pass. It preserves requested modes; UID/GID 0 and
mtime 0 are explicit lab choices because these instructions do not specify them.
CRC checks establish consistency with the extracted instructions, not a trusted
vendor signing chain; the original package hash is also rechecked.

The original rootfs has `/resources -> /mnt/resources`. The archive is not yet
attached to the guest. Its 2.53 GB of data should live on a separate disk rather
than in the current 1.5 GiB RAM guest's initramfs. A disk integration needs the
matching generic kernel's block/filesystem drivers and a read-only guest mount.

## Original compositor probe

`/usr/bin/wayland-viv-compositor` is a symlink to `winston`. Its help identifies
version `0.13.5 141205`. Binary strings identify `WL_COMPOSITOR_CONFIG` as the
configuration selector; the probe sets it to
`/etc/wayland/compositor_jci_display.conf`, sets a private `XDG_RUNTIME_DIR`, and
uses the original libraries from `/jci/lib`, `/usr/lib` and `/lib`.

The help command returns 0 and enumerates these configured plugins: ivi,
viv-output, notify, tsdev, xkb, screenshooter. The viv-output help explicitly
describes an output plugin using Vivante's 2D API. The vendor configuration
selects `/dev/fb0` and filtered keyboard, mouse and touchscreen nodes.

The bounded startup command logs missing filtered input devices and terminates
with SIGSEGV, shell status 139. The lab guest lacks `/dev/fb0` and `/dev/galcore`.
This is evidence of a graphics/device integration gap, but it does not locate
the faulting instruction or prove which absent device causes the crash.
No substitute driver, compositor, library or successful hardware stub was added.

Reproduce with `just guest-graphics-probe`; inspect
`runs/eu-v74-graphics-probe.log`. The probe's success status means all diagnostic
commands completed and the guest powered off; inspect the recorded compositor
exit codes for the graphics result. Opera and vehicle services are not started.

## Validation and next work

`just test` passes 12 tests, ShellCheck, ARM user-mode execution and QEMU machine
initialization. The graphics probe completes in a full-system guest and powers
off normally. The resource reconstruction verifies all 901 CRC32 records.

Next, attach resources as a read-only disk and obtain a compositor crash trace.
Use that trace to choose between implementing the relevant Vivante interface
and replacing the graphics path with a software implementation. A replacement
must account for Mazda's IVI Wayland extensions and original Opera ABI; simply
enabling VNC or substituting a modern compositor does not establish compatibility.
