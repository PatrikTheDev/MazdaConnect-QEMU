# Opt-in kernel matching Mazda's userspace address boundary

The user approved building and testing this profile on 2026-10-04 after the
original VBS monitor-pointer assertion and original kernel boundary were
established in finding 0025. This changes the lab environment, not the Mazda
synchronization library or its assertion.

```sh
just software-image
just software-kernel-build
just software-kernel-probe
just software-kernel-layout-report /software/<retained-run>
just software-mic-gain-test --kernel-profile vmsplit2g
just software-boot --kernel-profile vmsplit2g --renderer llvmpipe --intro-race-fix --time-deadline-fix --websockets-queue-fix
```

Stock remains the default for builds. Explicit `--kernel-profile stock`
rebuilds that profile; `software-run` reuses the currently built profile and
rejects an explicitly requested profile that differs. The shared software
lock prevents concurrent kernel/overlay builds and guests. The separate
Vivante checkout and reference firmware are not modified.

The source is Debian linux-source-6.1 version 6.1.176-1, already pinned by the
Docker snapshot. The builder additionally requires archive SHA256
`78cb82f50374e337d973c32ebf60d16e162589e45032db30f7a0d5295272de5e`.
It starts from the matching Debian ARMMP header configuration. Configuration
normalization showed these changes:

* `VMSPLIT_3G` becomes `VMSPLIT_2G`, deriving `PAGE_OFFSET=0x80000000` and
  `ARCH_MMAP_RND_BITS_MAX=15` instead of 16.
* `LOCALVERSION=-mazda-2g` identifies the distinct kernel/module release.
* The compiler text identifies the installed ARMEL cross-compiler rather
  than Debian's original kernel-package compiler. Both are GCC 12.2.0.
* `MODULE_SIG_KEY` points to the standard generated
  `certs/signing_key.pem`, rather than Debian's absent `output/signing_key.pem`.
  Signature configuration, including non-enforcement, remains unchanged.

Generated signing keys stay in the private Docker build volume. A fresh build
can produce different certificate/kernel hashes; this is a repeatable build
procedure, not a claim of bit-identical fresh outputs. Fixed build user, host,
timestamp and version avoid embedding host identity in the kernel banner.

The builder compiles zImage and modules, installs matching modules into a
separate package tree, and publishes a manifest only after all steps succeed.
Starting a rebuild invalidates the old manifest. The selector checks kernel
and normalized-config hashes before consuming a completed build. GPIO/VIP and
the lab HDA/microphone modules use that exact build tree. Disk, input, graphics
and sound dependencies also come from its installed modules; the overlay
replaces the base initramfs disk-module loader with matching modules.

## Verification status

The complete kernel/module build succeeded. The selected release is
`6.1.176-mazda-2g`; its normalized configuration SHA256 is
`4b6e7f52953935ea1b26b886e57f7b430d41cc2c2cf2e6e048b1f8032b087a03`
and zImage SHA256 is
`cfc2027c53e8396fccd6a534aedf92e3f2e3c21fb5dbbf144c28c885023e052d`.
Module packaging also checks each selected module's vermagic release.

Full original UI run `/software/test-dwdbwe6y` rendered HomeScreen.
The retained layout report passed: 3,427 ordinary mappings across 28 processes
satisfied the boundary, with 28 fixed ARM helper pages exempted. Original VBS
reached STARTED at 22.384 seconds, and all selected audio services reached
STARTED. There were no monitor assertions, module-loading errors, JavaScript
exceptions, heartbeat misses or database semaphore failures in the checked
logs. Two animation watchdogs and missing application-service subscriptions
remain; this is not a claim of complete infotainment emulation or a rendering
performance fix. The generic UI probe exits 1 intentionally for manual review;
its layout and service reports were checked separately.

`just software-mic-gain-test --kernel-profile vmsplit2g` passed in retained run
`/software/test-hl9xezfn`. Original ALSA speaker playback, microphone capture
and Bluetooth PCM transfers carried the expected tones. Both capture channels
measured full-gain RMS 5,651.8 and half-control RMS 697.9 (ratio 0.123), matching
the documented QEMU/PulseAudio adapter behavior. This verifies actual audio
transfers separately from service readiness. `just test` also passed: 13 unit
tests, shell checks and the ARM userspace/full-system smoke check.

The kernel probe retains the build manifest used for that run and a sequential
snapshot of nonempty process mappings immediately before browser shutdown.
The report requires the expected kernel release and all ordinary mapping ends
at or below 0x80000000. Only the fixed read-only ARM `[vectors]` helper page
at 0xffff0000 is exempt. Malformed/error records fail verification. These
snapshots establish observed address placement, not exhaustive monitor
contention coverage or every past/future allocation.
