/* Diagnostic backend: capture TX, deliberately leave requests unanswered. */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
#include "gpio/vip-transport.h"
int main(void)
{
    int fd=open("/dev/mazda_vip_transport",O_RDWR|O_NONBLOCK), raised=0;
    struct timespec start,now;
    if (fd<0) {perror("VIP transport");return 1;}
    setvbuf(stdout,NULL,_IONBF,0);
    clock_gettime(CLOCK_MONOTONIC,&start);
    puts("VIP_TRACE_READY: capture only; replies disabled");
    for (;;) {
        struct vip_packet packet;
        struct pollfd p={.fd=fd,.events=POLLIN};
        clock_gettime(CLOCK_MONOTONIC,&now);
        if (now.tv_sec-start.tv_sec>=12) break;
        if (!raised) {
            if (!ioctl(fd,VIP_RAISE_IRQ)) {raised=1;puts("VIP_TRACE_IRQ: one explicit diagnostic interrupt");}
            else if (errno!=ENOTCONN) {perror("VIP IRQ");close(fd);return 1;}
        }
        int result=poll(&p,1,100);
        if (result<0 && errno!=EINTR) {perror("VIP poll");close(fd);return 1;}
        if (result<=0) continue;
        ssize_t count=read(fd,&packet,sizeof(packet));
        if (count<0 && errno==EAGAIN) continue;
        if (count<VIP_HEADER_SIZE || packet.length>VIP_MAX_TRANSFER || count!=(ssize_t)(VIP_HEADER_SIZE+packet.length)) {
            fputs("Invalid VIP transport packet\n",stderr);close(fd);return 1;
        }
        printf("VIP_TX sequence=%u length=%u speed=%u mode=%u data=",packet.sequence,packet.length,packet.speed_hz,packet.mode);
        for (unsigned i=0;i<packet.length;i++) printf("%02x",packet.data[i]);
        putchar('\n');
    }
    close(fd);
    return 0;
}
