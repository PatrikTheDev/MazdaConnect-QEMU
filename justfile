set positional-arguments

default:
    @just --list

# Check the host and Docker connection.
doctor:
    bash scripts/doctor.sh

# Build the pinned Linux tool environment.
image-build:
    docker compose build lab

software-image:
    docker compose -f compose.software.yaml build lab

software-shell:
    docker compose -f compose.software.yaml run --rm lab bash

# Build and start the software UI. Connect with `just software-view`.
software-boot *args:
    docker compose -f compose.software.yaml run --rm --name mazda-software-live --service-ports lab python3 scripts/software/task.py boot "$@"

# Restart an already-built guest quickly; foreground Ctrl-C saves logs and stops it.
software-run *args:
    docker compose -f compose.software.yaml run --rm --name mazda-software-live --service-ports lab python3 scripts/software/task.py run "$@"

# Open the macOS VNC viewer while software-boot/software-run is running.
software-view:
    open vnc://127.0.0.1:5901

software-stop:
    docker stop --time 25 mazda-software-live

software-status:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py status

software-capture:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py capture

software-prepare:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/prepare.py

software-build:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/task.py build

software-test:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/task.py test

software-opera-test *args:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/task.py opera "$@"

software-browser-test:
    just software-opera-test --test-page --inspect-surface

software-video-test:
    just software-opera-test --seconds 60 --debug-services --capture-sequence --verify-video

software-vnc-test:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/task.py vnc

software-inspect binary start end *args:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/inspect_abi.py "$@"

shell:
    docker compose run --rm lab bash

versions:
    docker compose run --rm lab cat /opt/tool-versions.txt

# Import a package already placed in artifacts/. Requires a completed manifest.
firmware-import manifest package:
    docker compose run --rm lab python3 scripts/firmware/manage.py import "$1" "$2"

firmware-fetch manifest:
    docker compose run --rm lab python3 scripts/firmware/manage.py fetch "$1"

firmware-inspect manifest:
    docker compose run --rm lab python3 scripts/firmware/manage.py inspect "$1"

# Extract only the outer ZIP; filesystem payloads require format-specific handling.
firmware-extract manifest:
    docker compose run --rm lab python3 scripts/firmware/manage.py extract "$1"

# Analyze CMU150 payloads and rootfs metadata without running vendor scripts.
firmware-analyze manifest:
    docker compose run --rm lab python3 scripts/firmware/analyze.py "$1"

# Execute the original BusyBox with its original glibc in a disposable prefix.
firmware-probe manifest:
    docker compose run --rm lab python3 scripts/firmware/probe.py "$1"

firmware-boot-inspect manifest:
    docker compose run --rm lab python3 scripts/firmware/bootimage.py "$1"

firmware-resources manifest="config/firmware/cmu150-eu-74.00.324A.json":
    docker compose run --rm lab python3 scripts/firmware/resources.py "$1"

kernel-fetch:
    docker compose run --rm lab python3 scripts/guest/kernel.py

resources-disk identifier="cmu150-eu-74.00.324A":
    docker compose run --rm lab python3 scripts/guest/resources_disk.py "$1"

guest-build manifest="config/firmware/cmu150-eu-74.00.324A.json":
    docker compose run --rm lab python3 scripts/guest/build.py "$1"

# Requires kernel-fetch and guest-build; records the serial log in runs/.
guest-test profile="config/qemu/eu-v74-lab.json":
    docker compose run --rm lab python3 scripts/guest/check_boot.py "$1"

# Capture bounded attempts to start the original compositor in the lab guest.
guest-graphics-probe profile="config/qemu/eu-v74-lab.json":
    docker compose run --rm lab python3 scripts/guest/check_boot.py "$1" --probe

compositor-test profile="config/qemu/eu-v74-lab.json":
    docker compose run --rm lab python3 scripts/guest/check_boot.py "$1" --compositor

# Boot the Mazda userspace lab shell with the pinned generic kernel.
boot profile="config/qemu/eu-v74-lab.json":
    docker compose run --rm --service-ports lab python3 scripts/guest/boot.py "$1"

# Original compositor with IVI protocols, without a graphics output backend.
compositor profile="config/qemu/eu-v74-lab.json":
    docker compose run --rm lab python3 scripts/guest/boot.py "$1" --compositor

debug profile="config/qemu/eu-v74-lab.json":
    docker compose run --rm --service-ports lab python3 scripts/guest/boot.py "$1" --debug

# Run on the vehicle by piping this script to its existing root shell.
vehicle-script:
    @cat scripts/vehicle/inventory.sh

test:
    docker compose run --rm lab python3 -m unittest discover -s tests -v
    docker compose run --rm lab shellcheck scripts/doctor.sh scripts/vehicle/inventory.sh scripts/guest/smoke.sh overlays/lab/lab-init overlays/lab/run-compositor overlays/software/run-opera overlays/software/start-services
    docker compose run --rm lab bash scripts/guest/smoke.sh
