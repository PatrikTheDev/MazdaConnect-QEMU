/* Recovered checksum-enabled VIM transport; all frames are 20 bytes. */
#ifndef VIP_PROTOCOL_H
#define VIP_PROTOCOL_H
#include <stdbool.h>
#include <stdint.h>
#define VIP_FRAME_SIZE 20
#define VIP_ACK 0x3c1
#define VIP_NAK 0x3c2
struct vip_link {
    uint8_t last_rx[20], outbound[20];
    bool have_rx, queued, sent, hello_received, hello_acked;
    bool vbs_ready_pending, tau_pending;
    uint8_t vbs_ready, tau_state;
    unsigned control, tx_id, received, rejected, duplicates;
};
void vip_frame(uint8_t out[20], unsigned id, const uint8_t *payload, unsigned length);
int vip_decode(const uint8_t in[20]);
/* Returns a newly accepted application message ID, or -1. RX is chosen before
 * processing TX, preserving the delayed full-duplex acknowledgment contract. */
int vip_exchange(struct vip_link *link, const uint8_t tx[20], uint8_t rx[20]);
void vip_heartbeat(struct vip_link *link);
#endif
