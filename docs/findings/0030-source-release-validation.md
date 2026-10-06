# Source-only release preparation

Date: 2026-10-06. Input: CMU150 EU 74.00.324A, SHA-256
`3a506745c4ae65c21e0427714f377a4765b92e339cdbd6bf1b91ec398bb1a963`.
Host: Apple Silicon macOS, Docker Linux ARM64. This is a source-only release;
firmware and generated output remain private.

## Command and distribution changes

The justfile was reduced from 96 entries to 18 including default help. Everyday
commands cover setup, rebuild, start/restart, VNC viewing, input, capture, stop,
and verification. Specialized wrappers were removed; findings now use `just probe`
flags or `just dev SCOPE SCRIPT`. The underlying analysis tools remain available.

`just setup artifacts/PACKAGE.up` performs the complete local firmware-to-UI
pipeline. It never fetches firmware. Four compile workers are the default;
`--jobs 1..32` allows a different kernel worker count. The public viewer explicitly
selects the 2 GiB kernel, llvmpipe, and the three documented firmware corrections.
Lower-level research commands retain opt-in behavior.

Original project code/documentation now have GPL-2.0-only licensing, with external
inputs described separately in THIRD_PARTY.md. Git author attribution is retained.
Public CI builds only reference tooling and runs firmware-free checks, with full
reachable history checked for binary blobs/private-key headers. The guard is not
an exhaustive secret, provenance, or legal audit. Hosted CI has not run yet;
the workflow awaits publication of a GitHub repository.

## Reproduction evidence

- A clean source clone of `44fadef`, with no firmware, password file, or generated
  reports, passed `just test`: 19 unit tests, shell checks, publication guard, and
  ARM userspace/full-system QEMU initialization. Its reachable source history
  contained 361 blob versions and no rejected payloads.
- Complete setup used separately created, empty Docker volumes
  `mazda-qemu-release-reference-20261006` and
  `mazda-qemu-release-software-20261006`. No prior extracted trees, resource disks,
  sysroots, or compiled kernels were copied into them. Tooling-image layers could
  use Docker's existing cache.
- Setup completed in 49 minutes 52 seconds, including tooling-image builds and
  four-worker compilation. It checked 8,464 regular-file vendor MD5 records with
  zero mismatches, reconstructed 901 resource files with verified CRC32 values,
  built the read-only resource disk, and compiled Linux `6.1.176-mazda-2g` plus
  matching GPIO/VIP/HDA modules and the UI overlay.
- `just verify` passed in retained run `/software/test-769ktiaq`: every tested
  translation coordinate matched original Winston, with exact color-bar pixels
  and a Wayland frame callback. This is the compositor test, not full UI coverage.
- `just start --seconds 240 --start-delay 0` rendered the original home screen.
  Two Right keys followed by Enter opened Settings; Backspace returned to the
  home menu. The clock advanced from 09:22 to 09:23. QEMU reported a running guest
  and enabled VNC; Docker published it only at `127.0.0.1:5901`.
- Live run `/software/live-27p6vs9e` recorded all selected persistent services as
  STARTED and the intro service as STOPPED after completion. It had zero selected
  JavaScript exception, incoming-MMUI parse, missed-heartbeat, semaphore-create,
  or SMDB-handle failure markers, and four animation watchdog timeouts.

The first live run powered off cleanly at guest time 216.97 seconds, but the host
shell wrapper then exited 2: the wrapper file had been edited while its foreground
Docker command was running. The live branch now uses `exec docker compose ...`,
so Docker replaces that wrapper process. The lifecycle was rechecked separately
after this fix; see the final validation below.

## Final validation

- After the `exec` change, a 60-second bounded `just start` powered off at guest
  time 59.24 seconds and returned host exit 0, retaining `/software/live-tapy__8k`.
- `just restart --seconds 180 --start-delay 0` reused the built UI without
  compiling; an explicit `just stop` powered it off and both commands returned 0.
- The final `just test` passed 20 unit tests, shell checks, the working-tree/history
  publication guard, and both ARM/QEMU smoke checks.
- Temporary release-test volumes were removed after evidence collection. Normal
  lab volumes and source were preserved; ignored textual logs and captures remain
  available locally. Future isolated tests must rebuild their private artifacts.

Private logs and captures are under ignored `runs/release-*` and
`artifacts/release-*.png`. They are evidence retained locally, not release assets.
Remaining animation delays, incomplete VIP application responses, and absent
radio/navigation/Bluetooth integrations are documented in the README. No full UI
validation on Linux AMD64 or Windows is claimed.
