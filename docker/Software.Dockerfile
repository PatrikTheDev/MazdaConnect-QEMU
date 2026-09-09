FROM mazda-qemu-lab:local
RUN dpkg --add-architecture armel && \
    apt-get update && apt-get install -y --no-install-recommends python3-pyelftools && \
    mkdir -p /opt/mesa-armel /tmp/mesa-debs/partial && \
    apt-get -o Dir::State::status=/dev/null -o APT::Architecture=armel \
      -o APT::Architectures=armel -o Dir::Cache::archives=/tmp/mesa-debs \
      --download-only --no-install-recommends -y install \
      libegl1:armel libegl-mesa0:armel libgles2:armel libwayland-egl1:armel libgl1-mesa-dri:armel libvpx-dev:armel && \
    for package in /tmp/mesa-debs/*.deb; do dpkg-deb -x "$package" /opt/mesa-armel; done && \
    sha256sum /tmp/mesa-debs/*.deb > /opt/mesa-armel-packages.sha256 && \
    rm -rf /tmp/mesa-debs && \
    rm -rf /var/lib/apt/lists/*
