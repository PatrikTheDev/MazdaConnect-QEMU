#include <string.h>
#include "vip-protocol.h"
void vip_frame(uint8_t out[20], unsigned id, const uint8_t *payload, unsigned length)
{
    memset(out,0,20);
    out[0]=id; out[1]=id>>8;
    if (id==VIP_ACK || id==VIP_NAK) return; /* Vendor constants have no checksum. */
    out[2]=length;
    if (length) memcpy(out+3,payload,length);
    for (unsigned i=0;i<19;i++) out[19]+=out[i];
}
int vip_decode(const uint8_t in[20])
{
    unsigned id=in[0]|((unsigned)in[1]<<8);
    uint8_t sum=0;
    if (!id || id==VIP_ACK || id==VIP_NAK) return id;
    if (in[2]>16) return -1;
    for (unsigned i=0;i<19;i++) sum+=in[i];
    return sum==in[19] ? (int)id : -1;
}
int vip_exchange(struct vip_link *link,const uint8_t tx[20],uint8_t rx[20])
{
    unsigned control=link->control;
    bool was_sent=link->sent;
    int id=vip_decode(tx);
    if (!link->queued && link->hello_acked && link->vbs_ready_pending) {
        vip_frame(link->outbound,0x144,&link->vbs_ready,1);
        link->tx_id=0x144;link->queued=true;link->sent=false;
        link->vbs_ready_pending=false;
    }
    if (!link->queued && link->hello_acked && link->vbs_ready && link->tau_pending) {
        uint8_t payload[2]={0x08,link->tau_state};
        vip_frame(link->outbound,0x195,payload,2);
        link->tx_id=0x195;link->queued=true;link->sent=false;link->tau_pending=false;
    }
    link->control=0;
    memset(rx,0,20);
    if (control) vip_frame(rx,control,NULL,0);
    else if (link->queued && !link->sent) {
        memcpy(rx,link->outbound,20);link->sent=true;
    }
    if (id<0) {link->control=VIP_NAK;link->rejected++;return -1;}
    if (id==VIP_ACK || id==VIP_NAK) {
        link->have_rx=false;
        if (was_sent) {
            if (id==VIP_ACK) {
                if (link->tx_id==2) link->hello_acked=true;
                link->queued=false;link->sent=false;
            } else link->sent=false;
        }
        return -1;
    }
    if (!id) {link->have_rx=false;return -1;}
    if (link->have_rx && !memcmp(tx,link->last_rx,20)) {
        link->duplicates++;
        if (control!=VIP_ACK) link->control=VIP_ACK;
        return -1;
    }
    memcpy(link->last_rx,tx,20);link->have_rx=true;
    link->control=VIP_ACK;link->received++;
    if ((id&0x3ff)==2 && tx[2]==0 && !link->hello_received) {
        link->hello_received=true;
        vip_frame(link->outbound,2,NULL,0);link->tx_id=2;link->queued=true;link->sent=false;
    }
    if ((id&0x3ff)==0x144 && tx[2]==1 && tx[3]<=1 && link->hello_acked) {
        link->vbs_ready=tx[3];link->vbs_ready_pending=true;
    }
    if ((id&0x3ff)==0x1d5 && tx[2]==2 && tx[3]==0x95 && tx[4]==1
            && link->hello_acked && link->vbs_ready) link->tau_pending=true;
    return id&0x3ff;
}
void vip_heartbeat(struct vip_link *link)
{
    if (link->hello_acked && !link->queued && !link->vbs_ready_pending && !link->tau_pending) {
        vip_frame(link->outbound,0x31,NULL,0);link->tx_id=0x31;
        link->queued=true;link->sent=false;
    }
}
