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

# Check VNC passwords without rebuilding or touching the running Mazda guest.
software-vnc-auth-test:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/check_vnc_auth.py

software-stop:
    docker stop --time 25 mazda-software-live

software-status:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py status

software-capture:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py capture

software-key key:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/control.py key "$1"

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

# Compile only; does not change files mounted by an active viewer.
software-gpio-build:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/build_gpio.py

software-gpio-test:
    just software-opera-test --verify-gpio --seconds 60 --debug-services --capture-sequence

software-display-test:
    just software-opera-test --test-page --inspect-surface --verify-display --seconds 20

software-thermal-test:
    just software-opera-test --verify-gpio --verify-thermal --seconds 35 --debug-services

software-vim-probe:
    just software-opera-test --probe-vim --seconds 10 --debug-services

software-vbs-probe:
    just software-opera-test --seconds 20 --debug-services

software-audio-probe:
    just software-opera-test --probe-audio --seconds 10 --debug-services

software-audio-build:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/build_audio.py

software-audio-device-probe:
    just software-opera-test --audio-devices --microphone-tone 700 --probe-audio --probe-vip-service --seconds 10 --debug-services

software-audio-analyze directory *args:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/check_audio_samples.py "$@"

software-audio-services-probe:
    just software-opera-test --audio-devices --audio-services --probe-vip-service --seconds 30 --debug-services

software-render-probe:
    just software-opera-test --audio-devices --audio-services --probe-vip-service --live-output --trace-render --seconds 60 --debug-services --capture-sequence

software-render-sample:
    just software-opera-test --audio-devices --audio-services --probe-vip-service --live-output --sample-render --seconds 60 --debug-services --capture-sequence

software-ui-probe *args:
    just software-opera-test --audio-devices --audio-services --probe-vip-service --live-output --seconds 90 --debug-services --capture-sequence "$@"

software-startup-report run:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/startup_report.py "$@"

software-websockets-probe:
    just software-opera-test --renderer llvmpipe --probe-websockets --inspect-surface --seconds 20

software-intro-fix-test:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/check_intro_fix.py

software-intro-fix-probe *args:
    just software-ui-probe --renderer llvmpipe --intro-race-fix "$@"

software-audio-test:
    just software-opera-test --audio-devices --microphone-tone 700 --probe-audio --probe-vip-service --verify-audio --seconds 10 --debug-services

software-lvds-probe:
    just software-opera-test --probe-lvds --seconds 20 --debug-services

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
    docker compose run --rm lab shellcheck scripts/doctor.sh scripts/vehicle/inventory.sh scripts/guest/smoke.sh overlays/lab/lab-init overlays/lab/run-compositor overlays/software/run-opera overlays/software/start-services overlays/software/audio-check overlays/software/configure-audio
    docker compose run --rm lab bash scripts/guest/smoke.sh

# Verify the simulated SPI transport and VIP interrupt device, including reload.
software-vip-test:
    just software-opera-test --verify-vip --seconds 5

# Probe original VIM with the stateful VIP protocol peer.
software-vip-probe *args:
    just software-opera-test --probe-vip-service --seconds 20 --debug-services {{args}}

# Check protocol framing and exchange state in the target ARM ABI.
software-vip-protocol-test:
    docker compose -f compose.software.yaml run --rm lab python3 scripts/software/check_vip_protocol.py

# Require original VIM handshake plus VBS and system-service startup.
software-vbs-test:
    just software-opera-test --probe-vip-service --verify-vbs --seconds 20 --debug-services

# Verify original decoding of connected, standby, or disconnected TAU state.
software-tau-test state="connected":
    just software-opera-test --probe-vip-service --verify-tau --tau-state {{state}} --seconds 20 --debug-services
