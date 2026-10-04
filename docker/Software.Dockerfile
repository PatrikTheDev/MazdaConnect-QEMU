FROM mazda-qemu-lab:local
RUN dpkg --add-architecture armel && \
    apt-get update && apt-get install -y --no-install-recommends python3-pyelftools && \
    mkdir -p /opt/mesa-armel /tmp/mesa-debs/partial && \
    apt-get -o Dir::State::status=/dev/null -o APT::Architecture=armel \
      -o APT::Architectures=armel -o Dir::Cache::archives=/tmp/mesa-debs \
      --download-only --no-install-recommends -y install \
      libegl1:armel libegl-mesa0:armel libgles2:armel libwayland-egl1:armel libgl1-mesa-dri:armel libvpx-dev:armel libdbus-1-dev:armel && \
    for package in /tmp/mesa-debs/*.deb; do dpkg-deb -x "$package" /opt/mesa-armel; done && \
    sha256sum /tmp/mesa-debs/*.deb > /opt/mesa-armel-packages.sha256 && \
    rm -rf /tmp/mesa-debs && \
    rm -rf /var/lib/apt/lists/*

# Private software audio server: PCM recording plus a configurable input source.
RUN apt-get update && apt-get install -y --no-install-recommends \
      pulseaudio pulseaudio-utils qemu-system-gui && \
    rm -rf /var/lib/apt/lists/*

# Build the opt-in address-space profile from the pinned kernel source.
RUN apt-get update && apt-get install -y --no-install-recommends \
      flex bison bc libssl-dev libelf-dev dwarves && \
    rm -rf /var/lib/apt/lists/*

# Keep the target header archive's /lib directories away from the host's merged /usr.
RUN dpkg --add-architecture armhf && apt-get update && \
    apt-get install -y --no-install-recommends linux-kbuild-6.1=6.1.176-1 && \
    mkdir -p /tmp/kernel-headers/root /usr/src && cd /tmp/kernel-headers && \
    apt-get download linux-headers-6.1.0-50-armmp:armhf=6.1.176-1 \
      linux-headers-6.1.0-50-common=6.1.176-1 && \
    sha256sum *.deb > /opt/guest-kernel-headers.sha256 && \
    for package in *.deb; do dpkg-deb -x "$package" root; done && \
    cp -a root/usr/src/. /usr/src/ && \
    cd / && rm -rf /tmp/kernel-headers /var/lib/apt/lists/*

# Build the missing PCI HDA controller against the same pinned kernel release.
RUN apt-get update && apt-get install -y --no-install-recommends linux-source-6.1=6.1.176-1 && \
    mkdir -p /opt/guest-audio-source && \
    tar -xf /usr/src/linux-source-6.1.tar.xz -C /opt/guest-audio-source \
      --strip-components=4 linux-source-6.1/sound/pci/hda && \
    rm -rf /var/lib/apt/lists/*
