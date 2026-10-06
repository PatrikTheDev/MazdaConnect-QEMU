#!/usr/bin/env bash
set -euo pipefail
for tool in git docker just; do
    command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 1; }
done
docker compose version
docker info --format 'Docker: {{.OSType}}/{{.Architecture}}'
[[ $(docker info --format '{{.OSType}}') == linux ]] || {
    echo 'This lab requires a Docker runtime using Linux containers.' >&2; exit 1;
}
docker compose config --quiet
echo 'Host checks passed. Run just tools reference and just test, or follow just setup in README.md.'
