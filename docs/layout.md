# Layout and patch rules

| Path | Purpose |
| --- | --- |
| docker/ | Pinned tool environment |
| scripts/firmware/ | Acquisition, verification and extraction |
| scripts/guest/ | Guest assembly and execution |
| scripts/software/, src/software/ | Software rendering, simulated devices, local patch builders and diagnostics |
| scripts/release/ | Source publication checks |
| scripts/vehicle/ | Explicitly invoked read-only vehicle collection |
| config/firmware/ | Generic inventory template and per-package provenance |
| config/qemu/ | QEMU machine profiles |
| config/kernel/ | Pinned reference kernel metadata; custom build in scripts/software/build_kernel.py |
| patches/rootfs/VERSION/ | Ordered text changes to original files |
| patches/kernel/, patches/qemu/ | Patches against pinned upstream revisions |
| overlays/lab/, overlays/software/ | Guest launchers, test pages and lab service configuration |
| src/shims/, src/services/ | Future compatibility implementations |
| tests/ | Meaningful integrity and execution checks |
| docs/findings/, docs/decisions/ | Evidence and architectural decisions |

Each patch directory should contain a `series` file listing patches in application
order and a README recording purpose, input version/hash, evidence, and validation.
Fail on context mismatch; never apply fuzzy patches silently. Binary modifications
must validate input hash and expected original bytes and produce a separate output.

Build derived rootfs trees from a fresh verified input. Apply patches, then overlays,
then generate an image with a recorded manifest. Guest disk writes should go into a
per-run qcow2 overlay when disk-based boot is added. Never modify original packages.

Do not silently replace hardware services with success-returning stubs. Document the
observed dependency, proposed simulated behavior, and limits before implementing it.
Keep full firmware trees out of Git, including Git LFS. Keep private device data and
credentials out of public findings. No vehicle write or flash recipes are included.
