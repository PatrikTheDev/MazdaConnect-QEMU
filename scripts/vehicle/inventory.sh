#!/bin/sh
# Read-only commands, compatible with BusyBox sh. Output goes to stdout.
# Does not remount, dump flash, alter watchdogs, or collect credential files.
section() { printf '\n--- %s ---\n' "$1"; }
section kernel
uname -a
for item in /proc/cpuinfo /proc/cmdline /proc/mounts /proc/partitions /proc/mtd /proc/filesystems; do
    if [ -r "$item" ]; then section "$item"; cat "$item"; fi
done
section processes
ps
section devices
ls -l /dev/fb* /dev/dri /dev/galcore 2>/dev/null || :
section startup
ls -l /etc/init.d /etc/rc.d /jci /jci/opera 2>/dev/null || :
section libraries
ls -l /lib/ld* /lib/libc* /usr/lib/libEGL* /usr/lib/libGLES* 2>/dev/null || :
