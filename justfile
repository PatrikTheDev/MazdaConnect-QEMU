set positional-arguments

default:
    @just --list

# Check host dependencies and Docker access.
doctor:
    bash scripts/doctor.sh

# Build tooling images (all, reference, or software); no firmware required.
tools scope="all":
    bash scripts/lab.sh tools "$1"

# Import exact EU 74.00.324A from artifacts/ and build the complete software guest.
setup package *args:
    bash scripts/lab.sh setup "$@"

# Rebuild tooling, the 2 GiB kernel, and UI after source changes; setup required first.
build *args:
    bash scripts/lab.sh build "$@"

# Build and boot the documented software UI configuration; Ctrl-C stops it.
start *args:
    bash scripts/lab.sh start "$@"

# Boot the previously built UI without recompiling it.
restart *args:
    bash scripts/lab.sh restart "$@"

# Open macOS Screen Sharing, or print the VNC connection details.
view:
    bash scripts/lab.sh view

# Stop the live guest and retain logs.
stop:
    docker stop -t 25 mazda-software-live

# Inspect the live QEMU guest and VNC clients.
status:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py status

# Save the live framebuffer to artifacts/software-live.png.
capture:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py capture

# Send a key: right/left/up/down/ret, backspace (Back), m/n (rotary).
key key:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py key "$1"

# Verify compositor pixels and translation coordinates; requires setup.
verify *args:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/task.py test --kernel-profile vmsplit2g --verify-draw "$@"

# Firmware-free unit, shell, publication, and ARM/QEMU smoke checks.
test:
    docker compose run --rm lab python3 -m unittest discover -s tests -v
    docker compose run --rm lab shellcheck scripts/lab.sh scripts/doctor.sh scripts/vehicle/inventory.sh scripts/guest/smoke.sh overlays/lab/lab-init overlays/lab/run-compositor overlays/software/run-opera overlays/software/start-services overlays/software/audio-check overlays/software/configure-audio
    docker compose run --rm lab python3 scripts/release/check_publication.py
    docker compose run --rm lab bash scripts/guest/smoke.sh

# Bounded original-browser experiment; flags explicit, see docs/research.md.
probe *args:
    bash scripts/lab.sh probe "$@"

# Summarize service states and errors from a retained /software/ run.
report run *args:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/health_report.py "$@"

# Open a tooling shell (software or reference).
shell scope="software":
    bash scripts/lab.sh shell "$1"

# Run a research script: software, reference (guest), or firmware; see docs/research.md.
dev scope script *args:
    bash scripts/lab.sh dev "$@"
