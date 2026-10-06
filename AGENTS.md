# Project instructions

- Use the root justfile for tests and repeatable workflows. Keep its public recipe
  list small; specialized diagnostics belong behind `just probe` or `just dev`.
- Use Docker for compilers, Python tests, and guest tools. Request elevated access
  if the sandbox blocks Docker sockets or local ports. Report other local setup
  blockers instead of working around them; install missing trivial dependencies.
- Preserve original firmware inputs. Validate hashes and original bytes before
  patching, generate separate outputs, and document every behavioral adaptation.
- Ask before changing simulation architecture or introducing a workaround for an
  unmet binary contract. Report remaining limitations accurately.
- Never commit firmware, vendor binaries/assets, generated disks/initramfs files,
  private device inventories, credentials, keys, or runtime cores. No Git LFS for
  these inputs. Public CI must remain firmware-free.
- Keep research branches and worktrees independent. Do not modify a separate GPU
  experiment while working on the software-rendering path.
- Update current setup documentation and historical reproduction commands when
  changing the command interface. Commit coherent, verified changes regularly.
