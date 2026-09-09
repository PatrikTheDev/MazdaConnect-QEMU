/* Lab backend protocol, native little-endian ARM; not a Mazda wire format. */
#ifndef MAZDA_VIP_TRANSPORT_H
#define MAZDA_VIP_TRANSPORT_H
#include <linux/types.h>
#include <linux/ioctl.h>
#define VIP_MAX_TRANSFER 4096
struct vip_packet {
    __u32 sequence;
    __u32 length;
    __u32 speed_hz;
    __u32 mode;
    __u8 data[VIP_MAX_TRANSFER];
};
#define VIP_HEADER_SIZE 16
#define VIP_RAISE_IRQ _IO('V', 0)
struct cmu_registration { __s32 pid; __s32 gpio; };
#define CMU_REGISTER_IRQ _IOW('C', 0, struct cmu_registration)
#endif
