# Licensing and external inputs

Original project code and documentation are licensed under **GPL-2.0-only**;
see [LICENSE](LICENSE). Existing third-party notices take precedence for their
respective files. This license does not grant rights to Mazda firmware, artwork,
fonts, browser software, or other independently obtained inputs.

The repository supplies integration code and patch procedures. It does not
redistribute a firmware package, a complete firmware source tree, or a modified
Mazda application. The functional ABI declarations in `src/software/winston-abi.h`
describe the observed CMU150 interface. The reduced service configuration in
`overlays/software/sm.conf` records service names, paths, arguments, and dependencies
used by the lab; it is not a license grant for the original services.

External components downloaded or extracted during local builds include:

| Component | Source / notices |
| --- | --- |
| Linux 6.1.176 and Debian kernel packaging | Pinned Debian snapshot; kernel COPYING and per-file SPDX notices, generally GPL-2.0-only with applicable exceptions |
| HDA controller source | Unmodified `hda_intel.c` from the pinned Linux source; original notices retained in the private build tree |
| Mesa, Wayland, libvpx, D-Bus, PulseAudio and other runtime dependencies | Debian snapshot packages; their package copyright files and upstream licenses |
| QEMU, BusyBox, compilers, Python, archive and filesystem tools | Debian tooling image packages; their respective licenses |
| Original Mazda/JCI userspace, Opera, Vivante libraries and UI assets | User-supplied firmware; no redistribution permission asserted by this project |

`/usr/share/doc/*/copyright`, `/opt/tool-versions.txt`, and the package manifests
inside the tooling images identify installed dependencies. Some target packages
are extracted under `/opt/mesa-armel`, with copyright notices in its `usr/share/doc`.

Public releases are source-only. Before distributing compiled kernels, modules,
or tooling images, preserve applicable notices and provide the corresponding
source and build/install scripts required by their licenses. A generated
initramfs or Docker volume also contains proprietary userspace and must not be
treated as a redistributable kernel artifact.

Mazda and other product names identify interoperability targets. This project
is independent and is not endorsed by Mazda or the firmware vendors.
