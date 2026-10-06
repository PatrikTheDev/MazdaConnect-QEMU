# Contributing

Install Git, just, and Docker with Compose. Run `just tools reference` and
`just test` for firmware-free checks. See [README](README.md) for local UI setup
and [research commands](docs/research.md) for integration experiments.

Contributions are accepted under GPL-2.0-only. Retain existing notices and record
the source and license of any third-party code. Do not submit firmware packages,
extracted vendor files, modified vendor binaries, screenshots containing private
data, credentials, or generated guest images, including through Git LFS.

Keep the root justfile small: add an everyday command only when it has a distinct
purpose. Use `just probe` flags or `just dev SCOPE SCRIPT` for research procedures.
Update documentation when flags or public commands change.

For firmware changes, record the exact input version/hash, expected original
bytes, purpose, and validation. Generate a separate output and fail on mismatch;
never modify the reference package or silently apply fuzzy patches.
See [layout and patch rules](docs/layout.md).

Report what was tested, on which host architecture, and whether it required
private firmware. The public CI never fetches firmware. File bug reports with
sanitized text and reproduction commands; do not attach full runtime disks,
cores, firmware trees, or private device inventories.
