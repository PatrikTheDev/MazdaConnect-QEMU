#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "vip-protocol.h"
int main(void)
{
    uint8_t tx[20],rx[20],idle[20]={0},payload=0x31;
    struct vip_link link={0};
    vip_frame(tx,0x43,&payload,1);
    assert(tx[19]==0x75 && vip_decode(tx)==0x43);
    assert(vip_exchange(&link,tx,rx)==0x43 && vip_decode(rx)==0);
    assert(vip_exchange(&link,tx,rx)==-1 && vip_decode(rx)==VIP_ACK);
    assert(link.received==1 && link.duplicates==1);
    vip_frame(tx,2,NULL,0);
    assert(vip_exchange(&link,tx,rx)==2 && vip_decode(rx)==0);
    assert(vip_exchange(&link,tx,rx)==-1 && vip_decode(rx)==VIP_ACK);
    assert(vip_exchange(&link,idle,rx)==-1 && vip_decode(rx)==2);
    assert(!link.hello_acked);
    vip_frame(tx,VIP_NAK,NULL,0);
    vip_exchange(&link,tx,rx);
    vip_exchange(&link,idle,rx);assert(vip_decode(rx)==2);
    vip_frame(tx,VIP_ACK,NULL,0);
    vip_exchange(&link,tx,rx);assert(link.hello_acked && !link.queued);
    vip_heartbeat(&link);vip_exchange(&link,idle,rx);assert(vip_decode(rx)==0x31);
    vip_frame(tx,0x43,&payload,1);tx[19]++;
    assert(vip_exchange(&link,tx,rx)==-1);
    vip_exchange(&link,idle,rx);assert(vip_decode(rx)==VIP_NAK && link.rejected==1);
    vip_frame(tx,0x43,&payload,1);tx[2]=17;assert(vip_decode(tx)==-1);
    /* A readiness reply must not overwrite an unacknowledged heartbeat. */
    payload=1;vip_frame(tx,0x144,&payload,1);
    assert(vip_exchange(&link,tx,rx)==0x144 && link.vbs_ready_pending);
    vip_frame(tx,VIP_ACK,NULL,0);vip_exchange(&link,tx,rx);
    vip_exchange(&link,idle,rx);assert(vip_decode(rx)==0x144 && rx[2]==1 && rx[3]==1);
    vip_frame(tx,VIP_ACK,NULL,0);vip_exchange(&link,tx,rx);
    payload=2;vip_frame(tx,0x144,&payload,1);vip_exchange(&link,tx,rx);
    assert(!link.vbs_ready_pending);
    struct vip_link cold={0};payload=1;vip_frame(tx,0x144,&payload,1);
    vip_exchange(&cold,tx,rx);assert(!cold.vbs_ready_pending && !cold.queued);
    for (unsigned state=0;state<3;state++) {
        struct vip_link tau={.hello_acked=true,.vbs_ready=1,.tau_state=state};
        uint8_t request[2]={0x95,1};vip_frame(tx,0x1d5,request,2);
        assert(vip_exchange(&tau,tx,rx)==0x1d5 && tau.tau_pending);
        vip_exchange(&tau,tx,rx);assert(vip_decode(rx)==VIP_ACK);
        vip_exchange(&tau,idle,rx);
        assert(vip_decode(rx)==0x195 && rx[2]==2 && rx[3]==8 && rx[4]==state);
    }
    puts("VIP_PROTOCOL_OK: captured checksum, delayed ACK, duplicate filtering, hello ACK/NAK, heartbeat and corruption");
    return 0;
}
