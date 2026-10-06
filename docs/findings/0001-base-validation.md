# Base validation — 2026-09-09

Validation platform: Linux ARM64 container with Docker Compose.

Passed:

- `just doctor`: runtime access and Compose configuration.
- `just tools reference`: pinned Debian base and snapshot packages built successfully.
- `just test`: six Python tests, ShellCheck, a statically linked ARM probe executed
  through qemu-arm, and full-system QEMU virt-7.2 initialization queried over QMP.

Not established: Mazda firmware execution, Linux kernel boot, original UI rendering,
VNC end-to-end display, exact vehicle build/ABI, or EU package availability.

No firmware was downloaded and no connection to the vehicle was made.
