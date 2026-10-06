#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
cd "$(dirname "$0")/.."

compose() {
    local scope=$1
    shift
    case "$scope" in
        reference) docker compose -f compose.yaml "$@" ;;
        software) docker compose -f compose.software.yaml "$@" ;;
        *) echo 'Scope must be reference or software.' >&2; exit 2 ;;
    esac
}

images() {
    compose reference build lab
    compose software build lab
}

task() {
    compose software run --rm lab python3 scripts/software/task.py "$@"
}

action=${1:-help}
shift || true
case "$action" in
    tools)
        case "${1:-all}" in
            all) images ;;
            reference) compose reference build lab ;;
            software) compose software build lab ;;
            *) echo 'Tool scope must be all, reference, or software.' >&2; exit 2 ;;
        esac
        ;;
    setup)
        [[ $# == 1 ]] || { echo 'Usage: just setup artifacts/PACKAGE.up' >&2; exit 2; }
        [[ -f $1 ]] || { echo "Firmware package not found: $1" >&2; exit 2; }
        directory=$(cd "$(dirname "$1")" && pwd -P)
        [[ $directory == "$(pwd -P)/artifacts" ]] || {
            echo 'Place the firmware package directly in artifacts/ before setup.' >&2; exit 2;
        }
        [[ -n ${FIRMWARE_ZIP_PASSWORD:-} || -f .env ]] || {
            echo 'Set FIRMWARE_ZIP_PASSWORD in your shell or ignored .env before setup; see README.md.' >&2; exit 2;
        }
        bash scripts/doctor.sh
        images
        compose reference run --rm lab python3 scripts/firmware/prepare.py "artifacts/$(basename "$1")"
        compose software run --rm lab python3 scripts/software/prepare.py
        task kernel
        task build-ui --kernel-profile vmsplit2g
        echo 'Setup complete. Run just start, then just view in another terminal.'
        ;;
    build)
        images
        task kernel "$@"
        task build-ui --kernel-profile vmsplit2g
        ;;
    start|restart)
        mode=boot
        [[ $action != restart ]] || mode=run
        compose software run --rm --name mazda-software-live --service-ports lab \
            python3 scripts/software/task.py "$mode" --kernel-profile vmsplit2g \
            --renderer llvmpipe --intro-race-fix --time-deadline-fix --websockets-queue-fix "$@"
        ;;
    view)
        case "$(uname -s)" in
            Darwin) open vnc://127.0.0.1:5901 ;;
            *) echo 'Connect your VNC client to 127.0.0.1:5901 (password: mazda).' ;;
        esac
        ;;
    probe) task opera "$@" ;;
    shell) compose "${1:-software}" run --rm lab bash ;;
    dev)
        [[ $# -ge 2 ]] || { echo 'Usage: just dev SCOPE SCRIPT [ARGS...]' >&2; exit 2; }
        scope=$1
        script=$2
        shift 2
        case "$scope" in
            software) folder=software ;;
            reference) folder=guest ;;
            firmware) folder=firmware; scope=reference ;;
            *) echo 'Scope must be software, reference, or firmware.' >&2; exit 2 ;;
        esac
        [[ $script =~ ^[a-z][a-z0-9_]*$ && -f scripts/$folder/$script.py ]] || {
            echo "Unknown research script: $script" >&2; exit 2;
        }
        compose "$scope" run --rm lab python3 "scripts/$folder/$script.py" "$@"
        ;;
    *) echo "Unknown lab action: $action" >&2; exit 2 ;;
esac
