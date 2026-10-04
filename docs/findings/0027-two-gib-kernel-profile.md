# Opt-in kernel matching Mazda's userspace address boundary

The user approved building and testing this profile on 2026-10-04 after the
original VBS monitor-pointer assertion and original kernel boundary were
established in finding 0025. This changes the lab environment, not the Mazda
synchronization library or its assertion.

```sh
just software-image
just software-kernel-build
just software-websockets-fix-probe --kernel-profile vmsplit2g --seconds 90
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

`just test` passed for the initial integration. The custom kernel compilation
is underway. Its boot, runtime address layout, original VBS/audio operation
and UI have not yet been verified. No successful custom-kernel startup is
claimed at this checkpoint.
