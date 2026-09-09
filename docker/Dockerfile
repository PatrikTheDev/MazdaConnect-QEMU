FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171
# Snapshot packages as well as the base image for repeatable rebuilds.
RUN rm -f /etc/apt/sources.list.d/debian.sources && \
    printf '%s\n' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260908T000000Z bookworm main' \
    > /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 jq ripgrep file xxd p7zip-full unzip \
    tar gzip xz-utils cpio patch make gcc gcc-arm-linux-gnueabi \
    binutils-arm-linux-gnueabi gdb-multiarch strace \
    qemu-user qemu-system-arm qemu-utils device-tree-compiler \
    e2fsprogs squashfs-tools mtd-utils shellcheck kmod && \
    dpkg-query -W > /opt/tool-versions.txt && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends \
    libc6-dev libc6-dev-armel-cross && \
    dpkg-query -W > /opt/tool-versions.txt && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["bash"]
