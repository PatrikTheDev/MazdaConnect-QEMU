# VBS monitor pointer exceeds the original tag boundary

The full-UI run `/software/test-vbaq7rpb` rendered HomeScreen but failed VBS and
several dependent audio services. Its SM log contains the original assertion
`Sync::inflateTasuki ... MONITOR_MAXIMUM >= mid`, at Sync.cpp line 803.

## Original binary evidence

`libjci.so` contains local function `Sync::inflateTasuki` at 0xf1020. Its second
argument is the Tasuki monitor pointer, copied into r4. At 0xf116c it compares
r4 with zero, and at 0xf1180 branches on signed less-than to the assertion at
0xf13a0. Thus an address with bit 31 set violates this assertion. On success,
0xf118c sets bit 31 on the pointer before storing it in the synchronized
object. This is a pointer-tagging restriction, not exhaustion of a monitor
counter or excessive kernel thread IDs.

The pinned generic Debian kernel has `CONFIG_VMSPLIT_3G=y` and
`CONFIG_PAGE_OFFSET=0xC0000000`. Its userspace can receive allocations above
the synchronization library's 0x7fffffff tag boundary. A contention path that
inflates a monitor can expose this mismatch even after other boots succeeded.
Inspection of the original vehicle kernel confirms a linked kernel virtual
base of 0x80000000, consistent with the 2 GiB userspace boundary required by
this pointer representation. It has no embedded configuration, so this is
evidence from its boot code rather than a recovered `CONFIG_VMSPLIT` setting.

## Original kernel layout evidence

```sh
just software-original-kernel-layout
```

This read-only recipe verifies the EU 74.00.324A zImage, decodes its LZO stream
with liblzo2, validates header and block Adler32 checksums, and verifies the
decoded image hash. The actual stream starts at byte 6116; the earlier LZO
magic at byte 5792 belongs to the decompressor's constant table.

The zImage SHA256 is
`57fe0cda7c1f994a6ca6b3cce7d9cf247f3b5607ebf1ddc12f02598662d5e240`.
The decoded 4,568,900-byte kernel SHA256 is
`b45da4c4e862f8261656ae74443a8a36582a861d9dfa42d8fdadee7a72a0cb85`.
Its ARM head contains linked self-address 0x80008048 at offset 0x48 and
kernel-base literal 0x80000000 at offset 0x4c. Page-table setup also adds
0x80000000 at offset 0xec. No `IKCFG_ST` embedded-configuration marker is
present. This establishes the relevant original address boundary without
executing or modifying the vehicle kernel.

## Retained crash evidence

```sh
just software-vbs-core-report /software/test-vbaq7rpb --thread 26 --frame 5
just software-inspect jci/lib/libjci.so 0xf1020 0xf14f4
```

The retained file is named `compositor.core` because the harness used that
core-pattern name before browser startup. `file` identifies its actual command
as `/jci/sm/sm_svclauncher -l jciVBS /jci/vbs/svcjcivbs.so 0 -a`.

Thread 26 (LWP 338) aborted through `__assert_fail`, `Sync::inflateTasuki`,
`Sync::aquire`, and `Thread::start`. The assertion frame's stack at 0xac5e7c88
contains 0xac400490 in both argument slots populated by the assertion path
(SP+4 and SP+8). That address exceeds 0x7fffffff. Do not use reconstructed r4
in that frame as the original pointer: the assertion path and unwinding have
already changed its reported value.

GDB warns about missing transient shared-memory mappings, a core/executable
match, and unavailable matching libthread_db. The identified command, original
symbol offsets, assertion text, and saved stack arguments corroborate the
diagnosis; deeper stacks that GDB cannot unwind are not treated as evidence.
The report disables Python autoloads and rejects cores not identified as VBS.

## Proposed environment correction

A separate guest kernel profile with `CONFIG_VMSPLIT_2G` would keep userspace
addresses below the tag boundary. It requires building a pinned kernel and
matching guest modules, then verifying memory layout, monitor contention,
original VBS/audio startup, and the full UI. This preserves the original
synchronization implementation and assertion. It is an environment design
change pending a decision; no kernel split or firmware behavior has been
changed by this investigation.

Disabling the assertion alone would not fix the representation: bit 31 is
already occupied by a real pointer in the failing case. Allocator tuning or
address-placement tricks have not been introduced.
