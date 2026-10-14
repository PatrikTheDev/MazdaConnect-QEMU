# Research commands

The root justfile exposes everyday setup, build, viewer, and test commands.
Specialized experiments use two entry points; there are no hidden alias recipes.

## Bounded browser experiments

`just probe` builds an Opera guest, runs `scripts/software/check.py`, and retains
its logs and output disk. It keeps the original research defaults: stock kernel,
softpipe, and no firmware corrections. Select flags explicitly. `--kernel-profile`
is handled by the build coordinator; other flags go to the checker.

```sh
# List checker flags without assembling a guest.
just dev software check --help

# Original UI with the same choices as the everyday viewer.
just probe --kernel-profile vmsplit2g --renderer llvmpipe --intro-race-fix --time-deadline-fix --websockets-queue-fix --time-services --audio-devices --audio-services --probe-vip-service --live-output --capture-sequence --seconds 90

# Controlled geometry test in original Opera.
just probe --kernel-profile vmsplit2g --test-page --inspect-surface --renderer llvmpipe --probe-draw-positions --verify-draw --seconds 10

# Verify original VIM/VBS handshake with the simulated transport.
just probe --kernel-profile vmsplit2g --probe-vip-service --verify-vbs --seconds 20 --debug-services

# Verify HDA microphone gain with deterministic audio samples.
just probe --kernel-profile vmsplit2g --audio-devices --microphone-tone 700 --probe-audio --probe-vip-service --verify-audio --verify-mic-gain --seconds 10 --debug-services
```

The generic original-UI diagnostic deliberately exits 1 after retaining evidence.
It requires pixel/log inspection and does not claim end-to-end UI success. Specific
`--verify-*` branches have their own pass conditions; read the checker and findings
before treating an exit code as a broader readiness claim.

## Specialized scripts

`just dev SCOPE SCRIPT [ARGS...]` runs an existing Python script by its stem:

| Scope | Directory | Container / data |
| --- | --- | --- |
| `firmware` | `scripts/firmware/` | Reference tooling; `/lab` writable |
| `reference` | `scripts/guest/` | Reference tooling; `/lab` writable |
| `software` | `scripts/software/` | Software tooling; reference `/lab` read-only, `/software` writable |

Script names cannot contain path separators. Arguments are passed directly,
without shell evaluation. Examples:

```sh
just dev firmware manage inspect config/firmware/cmu150-eu-74.00.324A.json
just dev firmware bootimage config/firmware/cmu150-eu-74.00.324A.json
just dev reference check_boot config/qemu/eu-v74-lab.json --compositor
just dev software task kernel --jobs 2
just dev software check_vip_protocol
just dev software check_vnc_auth
just dev software kernel_layout_report /software/RETAINED-RUN
just dev software frame_report /software/RETAINED-RUN --timeline
just dev software transition_report /software/RETAINED-RUN
just dev software inspect_abi jci/lib/libjci.so 0xf1020 0xf14f4
```

Build/run commands should use the coordinator `task` so its exclusive lock protects
shared software artifacts. For unpatched or stock-kernel live experiments:

```sh
just dev software task boot --kernel-profile stock --renderer softpipe
```

This lower-level command does not publish VNC ports. Use an explicit
`docker compose -f compose.software.yaml run --rm --service-ports lab python3 scripts/software/task.py boot ...`
when a research guest needs host access. The everyday `just start` handles ports.

For the original developer HTTP server, use the live runner:

```sh
MAZDA_INSTANCE=dev-server MAZDA_VNC_PORT=5902 just start --remote-gui --seconds 160 --start-delay 0
```

Open `http://127.0.0.1:8080/` after `LAB_DEV_SERVER_STARTED`. The native GUI
WebSocket services also need time to start. The live wrapper publishes HTTP and
all three WebSocket ports only with `--developer-mode` or `--remote-gui`; a raw Compose research
launch needs explicit `--publish` mappings instead of `--service-ports` for these
ports (Compose does not allow both options together). See the README for named
instances, runtime snapshots and the fixed WebSocket port constraint.

To verify the running instance through its container network interface:

```sh
MAZDA_INSTANCE=dev-server just dev software check_dev_server
```

This checks the HTTP index and browser compatibility asset, then validates all
three WebSocket upgrade responses, accept keys and native subprotocols. It does
not prove desktop rendering or navigation; see the developer-server finding for
the recorded browser validation.

Findings retain the flags and profile choices of their original experiments.
Old wrapper names have been expanded into these entry points; long commands in
historical notes intentionally preserve their evidence scope. Older findings
describe the state at their recorded date, not the latest working UI.

Run `just report /software/RETAINED-RUN` for the usual service-health summary.
Other reports use `just dev software SCRIPT /software/RETAINED-RUN`. Copying a
runtime disk, core, or sysroot into a public report can expose proprietary code;
share sanitized summaries instead.
