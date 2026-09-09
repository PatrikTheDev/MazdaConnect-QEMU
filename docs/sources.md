# Research sources

Consulted 2026-09-09. Community descriptions must be checked against our exact EU build.

- https://silverchris.github.io/mazda-cmu-documentation/update-files.html — outer package structure.
- https://github.com/GrayHatter/Mazda-IVI-Knowledgebase — i.MX6/Opera/Wayland observations.
- https://github.com/rpendleton/mazda-toolchain — historical toolchain configuration.
- https://www.qemu.org/docs/master/system/arm/virt.html — generic ARM board.
- https://www.qemu.org/docs/master/system/arm/sabrelite.html — i.MX6 devices supported by QEMU.
- https://www.qemu.org/docs/master/user/main.html — userspace emulation limits.
- https://docs.docker.com/engine/storage/volumes/ — persistent Linux storage.

The online QEMU development manual can describe newer features than our pinned
Debian QEMU. Test launcher arguments against the installed version.

A North American v74 package was identified during initial research, but is not
selected for this EU baseline. EU 74.00.324A was subsequently acquired from a public
Yandex mirror and hash-verified; see findings/0002-eu-v74-analysis.md.

- https://www.mazdaklan.cz/threads/aktualizace-systemu-mzd-connect-s-dotykovym-displejem-2014-2018.54/page-23 — first-hand checksum report and public mirror link.
- https://disk.yandex.ru/d/QIjY9lRX3NugBA — acquired package source.
- https://www.fabidouille.com/?p=151 — published archive password.
- https://x53.ninja/projects/m3/m3-updates/ — prior research on update instruction structure.
