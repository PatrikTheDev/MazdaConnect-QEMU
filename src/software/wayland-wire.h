/* Small blocking Wayland wire client; caller owns connection and alarm deadline. */
#include <poll.h>
#include <signal.h>
static int sock;
static volatile sig_atomic_t wire_stopping;
static void receive(void *data, size_t length) {
    char *p=data;
    while (length) {
        if (wire_stopping) exit(0);
        struct pollfd ready={.fd=sock,.events=POLLIN};
        int status=poll(&ready,1,1000);
        if (!status || (status<0 && errno==EINTR)) continue;
        if (status<0) {perror("Wayland poll");exit(1);}
        ssize_t n=read(sock,p,length);
        if (n<0 && errno==EINTR) continue;
        if (n<=0) {perror("Wayland read");exit(1);}
        p+=n; length-=n;
    }
}
static void request(uint32_t object, unsigned opcode, const uint32_t *args, size_t count, int fd) {
    uint32_t wire[128]={object, ((count*4+8)<<16)|opcode};
    if (count>126) exit(2);
    memcpy(wire+2,args,count*4);
    struct iovec iov={wire,count*4+8};
    char control[CMSG_SPACE(sizeof(int))]={0};
    struct msghdr msg={.msg_iov=&iov,.msg_iovlen=1};
    if (fd>=0) {
        msg.msg_control=control; msg.msg_controllen=sizeof(control);
        struct cmsghdr *c=CMSG_FIRSTHDR(&msg);
        c->cmsg_level=SOL_SOCKET; c->cmsg_type=SCM_RIGHTS; c->cmsg_len=CMSG_LEN(sizeof(int));
        memcpy(CMSG_DATA(c),&fd,sizeof(fd));
    }
    if (sendmsg(sock,&msg,0)!=(ssize_t)iov.iov_len) {perror("Wayland send");exit(1);}
}
static void bind_global(uint32_t global,const char *name,uint32_t id) {
    uint32_t args[64]={global,strlen(name)+1};
    unsigned padded=(args[1]+3)/4;
    memcpy(args+2,name,args[1]);
    args[2+padded]=1; args[3+padded]=id;
    request(2,0,args,4+padded,-1);
}
