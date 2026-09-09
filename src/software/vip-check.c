/* Exercise the SPI transport through upstream spidev, including failure paths. */
#include <errno.h>
#include <fcntl.h>
#include <linux/spi/spidev.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>
#include "gpio/vip-transport.h"
#define CHECK(x) do { if (!(x)) {fprintf(stderr,"VIP check line %d: %s (errno %d)\n",__LINE__,#x,errno);exit(1);} } while (0)
int main(void)
{
    int sockets[2], status;
    char byte='R';
    uint8_t mode=3,bits=8,tx[]={0x10,0x00,0xff,0x41},rx[4]={0};
    uint32_t speed=4000000;
    struct spi_ioc_transfer transfer={.tx_buf=(uintptr_t)tx,.rx_buf=(uintptr_t)rx,.len=sizeof(tx)};
    sigset_t set; sigemptyset(&set); sigaddset(&set,SIGIO); CHECK(sigprocmask(SIG_BLOCK,&set,NULL)==0);
    alarm(15);
    int spi=open("/dev/spidev1.0",O_RDWR); CHECK(spi>=0);
    CHECK(ioctl(spi,SPI_IOC_WR_MODE,&mode)==0);
    CHECK(ioctl(spi,SPI_IOC_WR_BITS_PER_WORD,&bits)==0);
    CHECK(ioctl(spi,SPI_IOC_WR_MAX_SPEED_HZ,&speed)==0);
    CHECK(ioctl(spi,SPI_IOC_MESSAGE(1),&transfer)==-1 && errno==ENOTCONN);
    int cmu=open("/dev/cmu_io",O_RDWR); CHECK(cmu>=0);
    struct cmu_registration reg={.pid=getpid(),.gpio=42};
    CHECK(ioctl(cmu,CMU_REGISTER_IRQ,&reg)==0);
    reg.gpio=9; CHECK(ioctl(cmu,CMU_REGISTER_IRQ,&reg)==-1 && errno==EINVAL);
    CHECK(socketpair(AF_UNIX,SOCK_STREAM,0,sockets)==0);
    pid_t child=fork(); CHECK(child>=0);
    if (!child) {
        struct vip_packet packet;
        close(sockets[0]); close(spi); close(cmu);
        int backend=open("/dev/mazda_vip_transport",O_RDWR); CHECK(backend>=0);
        CHECK(open("/dev/mazda_vip_transport",O_RDWR)==-1 && errno==EBUSY);
        CHECK(write(sockets[1],&byte,1)==1);
        CHECK(read(backend,&packet,1)==-1 && errno==EMSGSIZE);
        CHECK(read(backend,&packet,sizeof(packet))==VIP_HEADER_SIZE+sizeof(tx));
        CHECK(packet.length==sizeof(tx) && packet.speed_hz==speed && packet.mode==mode);
        CHECK(!memcmp(packet.data,tx,sizeof(tx)));
        for (unsigned i=0;i<sizeof(tx);i++) packet.data[i]^=0x5a;
        packet.sequence--; CHECK(write(backend,&packet,VIP_HEADER_SIZE+sizeof(tx))==-1 && errno==ESTALE);
        packet.sequence++;
        CHECK(ioctl(backend,VIP_RAISE_IRQ)==0);
        CHECK(write(backend,&packet,VIP_HEADER_SIZE+sizeof(tx))==VIP_HEADER_SIZE+sizeof(tx));
        /* Read but do not answer the second transfer: it must time out. */
        CHECK(read(backend,&packet,sizeof(packet))==VIP_HEADER_SIZE+sizeof(tx));
        CHECK(read(sockets[1],&byte,1)==1);
        CHECK(write(backend,&packet,VIP_HEADER_SIZE+sizeof(tx))==-1 && errno==ESTALE);
        close(backend); close(sockets[1]); _exit(0);
    }
    close(sockets[1]); CHECK(read(sockets[0],&byte,1)==1);
    CHECK(ioctl(spi,SPI_IOC_MESSAGE(1),&transfer)==sizeof(tx));
    for (unsigned i=0;i<sizeof(tx);i++) CHECK(rx[i]==(tx[i]^0x5a));
    struct timespec timeout={.tv_sec=1}; CHECK(sigtimedwait(&set,NULL,&timeout)==SIGIO);
    CHECK(ioctl(spi,SPI_IOC_MESSAGE(1),&transfer)==-1 && errno==ETIMEDOUT);
    CHECK(write(sockets[0],&byte,1)==1);
    CHECK(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
    close(sockets[0]);close(cmu);
    int backend=open("/dev/mazda_vip_transport",O_RDWR); CHECK(backend>=0);
    CHECK(ioctl(backend,VIP_RAISE_IRQ)==-1 && errno==ENOTCONN);
    close(backend);
    CHECK(ioctl(spi,SPI_IOC_MESSAGE(1),&transfer)==-1 && errno==ENOTCONN);
    close(spi);
    puts("VIP_TRANSPORT_OK: SPI bytes, timeout, stale responses, exclusive backend, IRQ registration and cleanup");
    return 0;
}
