/* Stateful VIP transport peer. Unimplemented application commands are logged. */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
#include "gpio/vip-transport.h"
#include "vip-protocol.h"
static long milliseconds(void) {
    struct timespec time;clock_gettime(CLOCK_MONOTONIC,&time);
    return time.tv_sec*1000+time.tv_nsec/1000000;
}
int main(int argc, char **argv)
{
    unsigned tau=1;
    if (argc!=1) {
        if (argc!=3 || strcmp(argv[1],"--tau-state")) return 2;
        if (!strcmp(argv[2],"standby")) tau=0;
        else if (!strcmp(argv[2],"connected")) tau=1;
        else if (!strcmp(argv[2],"disconnected")) tau=2;
        else {fputs("Invalid simulated TAU state\n",stderr);return 2;}
    }
    int fd=open("/dev/mazda_vip_transport",O_RDWR|O_NONBLOCK);
    struct vip_link link={.tau_state=tau};
    long next_irq=0,next_heartbeat=0;
    bool reported=false;
    if (fd<0) {perror("VIP transport");return 1;}
    setvbuf(stdout,NULL,_IONBF,0);
    printf("VIP_SERVICE_READY: simulated VIP transport; TAU state=%u\n",tau);
    for (;;) {
        struct vip_packet packet;
        struct pollfd p={.fd=fd,.events=POLLIN};
        long now=milliseconds();
        if (now>=next_heartbeat) {vip_heartbeat(&link);next_heartbeat=now+1000;}
        /* Lab VIP offers a transfer slot every 100 ms; no readiness is asserted. */
        if (now>=next_irq) {
            if (ioctl(fd,VIP_RAISE_IRQ) && errno!=ENOTCONN && errno!=ESRCH) {perror("VIP IRQ");return 1;}
            next_irq=now+100;
        }
        int ready=poll(&p,1,20);
        if (ready<0 && errno!=EINTR) {perror("VIP poll");return 1;}
        if (ready<=0) continue;
        ssize_t count=read(fd,&packet,sizeof(packet));
        if (count<0 && errno==EAGAIN) continue;
        if (count!=VIP_HEADER_SIZE+20 || packet.length!=20 || packet.mode!=3) {
            fputs("Unsupported VIP transfer shape\n",stderr);return 1;
        }
        uint8_t response[20];
        int id=vip_exchange(&link,packet.data,response);
        if (id>=0) {
            printf("VIP_MESSAGE id=0x%03x length=%u payload=",id,packet.data[2]);
            for (unsigned i=0;i<packet.data[2];i++) printf("%02x",packet.data[3+i]);
            printf(" handler=%s\n",id==2 ? "hello" : id==0x30 ? "host-heartbeat" : id==0x144 && packet.data[2]==1 && packet.data[3]<=1 && link.hello_acked ? "vbs-ready" : id==0x1d5 && packet.data[2]==2 && packet.data[3]==0x95 && packet.data[4]==1 && link.vbs_ready ? "tau-status" : "unimplemented");
        }
        if (vip_decode(response)==0x195) printf("VIP_TAU_STATUS state=%u\n",response[4]);
        for (unsigned i=0;i<20;i++) packet.data[i]=response[i];
        if (write(fd,&packet,count)!=count) {perror("VIP response");return 1;}
        if (link.hello_acked && !reported) {puts("VIP_HELLO_ACKED");reported=true;}
    }
}
