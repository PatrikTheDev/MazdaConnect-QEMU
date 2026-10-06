# Source-only release procedure

The public distribution consists of Git source files. Supported firmware inputs
and generated Mazda userspace remain local; GPL-2.0-only covers original project
work, not independently obtained proprietary inputs. See [THIRD_PARTY](../THIRD_PARTY.md).

## Before publishing

1. Run `just tools reference` and `just test`. Review staged files and the diff.
   The publication guard checks tracked working-tree files for binary content,
   private-key headers, and generated-data paths. It is not an exhaustive secret
   scanner, history audit, or provenance/legal review.
2. Inspect reachable Git history for accidental firmware or secrets when adding
   branches or importing external work. Ignoring a file does not remove old Git
   objects. Normal author names/emails are intentional public attribution here;
   no history rewrite is needed solely to hide that metadata.
3. Verify the documented bootstrap with private firmware in empty test volumes,
   then run `just verify` and inspect a bounded live UI startup. Record host
   architecture, source commit, package hash, and results. Do not use existing
   extracted trees as proof of a fresh bootstrap.
4. Confirm the README states current working screens, simulation limits, tested
   hosts, and the exact supported firmware version.
5. Publish only the intended source branch/tag. Do not attach firmware, screenshots
   or recordings of vendor assets, generated guest images, vendor libraries,
   Docker volume exports, private keys, or unreviewed debug artifacts. The Actions
   workflow uses no firmware and uploads no runtime artifacts.

## Isolated private bootstrap

The two volume overrides allow validation without replacing the normal lab data:

```sh
export MAZDA_REFERENCE_VOLUME=mazda-qemu-release-reference
export MAZDA_SOFTWARE_VOLUME=mazda-qemu-release-software
just setup artifacts/cmu150_EU_74.00.324A_update.up
just verify
just start --seconds 180 --start-delay 0
```

Keep those variables in the same shell for subsequent commands; VNC/key/capture
commands in a second terminal need the same overrides. A first test must use
names that do not already exist. Check Docker storage capacity first. The test
retains its private volumes for diagnosis; delete only those explicitly named
test volumes after stopping all test containers. There is no automatic data wipe.

## Reproducibility boundaries

The tooling base digest, Debian snapshot, firmware size/hash, and kernel source
hash are pinned. The custom kernel is built from Debian Linux 6.1.176-1 with a
2 GiB userspace split and matching modules. All Mazda patches are generated from
hash-checked input into separate outputs. A rooted car is unnecessary.

The procedure depends on user-supplied firmware/password and availability of the
Debian snapshot. It does not promise byte-identical kernel binaries: private
module-signing keys are generated locally. Host architectures other than the
recorded validation platform need their own complete UI checks. Public CI checks
tooling and source only; it cannot certify Mazda service behavior.

If distributing Linux-only binaries later, provide the exact corresponding source,
configuration, build/install scripts, and applicable notices alongside them.
A firmware-containing initramfs is not a Linux-only binary. Follow the
[GPLv2 requirements](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
and the licenses of every bundled dependency before adding binary releases.
