#!/usr/bin/env bash
set -euo pipefail
task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT
cat > "$task_tmp/hello.c" <<'EOF'
#include <stdio.h>
int main(void) { puts("ARM emulation works"); return 0; }
EOF
# This compiler is for lab probes, not yet the Mazda ABI/sysroot.
arm-linux-gnueabi-gcc -static -o "$task_tmp/hello" "$task_tmp/hello.c"
test "$(qemu-arm "$task_tmp/hello")" = 'ARM emulation works'
qemu-system-arm -M virt-7.2,highmem=off -cpu cortex-a15 -accel tcg \
    -display none -nic none -S -qmp stdio <<'EOF' > "$task_tmp/qmp.log"
{"execute":"qmp_capabilities"}
{"execute":"query-status"}
{"execute":"quit"}
EOF
rg '"status": "prelaunch"' "$task_tmp/qmp.log" >/dev/null
echo 'ARM userspace execution and full-system QEMU initialization passed.'
