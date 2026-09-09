/* A real wl_shm client for checking the vendor compositor's CPU output. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include "wayland-wire.h"
int main(int argc,char **argv) {
    if (argc!=2) return 2;
    alarm(15);
    sock=socket(AF_UNIX,SOCK_STREAM,0);
    struct sockaddr_un addr={.sun_family=AF_UNIX};
    if (strlen(argv[1])>=sizeof(addr.sun_path)) return 2;
    strcpy(addr.sun_path,argv[1]);
    if (connect(sock,(void *)&addr,sizeof(addr))) {perror("connect");return 1;}
    request(1,1,(uint32_t[]){2},1,-1);
    request(1,0,(uint32_t[]){3},1,-1);
    uint32_t compositor=0, shm=0, shell=0;
    for (;;) {
        uint32_t header[2],args[4096];
        receive(header,8);
        unsigned size=header[1]>>16,opcode=header[1]&65535;
        if (size<8 || size%4 || size-8>sizeof(args)) return 1;
        receive(args,size-8);
        if (header[0]==1 && opcode==0) {fputs("Wayland error\n",stderr);return 1;}
        if (header[0]==2 && opcode==0) {
            if (size<20 || !args[1] || args[1]>size-20 || ((char *)(args+2))[args[1]-1]) return 1;
            const char *name=(char *)(args+2);
            if (!strcmp(name,"wl_compositor")) compositor=args[0];
            if (!strcmp(name,"wl_shm")) shm=args[0];
            if (!strcmp(name,"wl_shell")) shell=args[0];
        }
        if (header[0]==3 && opcode==0) break;
    }
    if (!compositor || !shm || !shell) return 1;
    bind_global(compositor,"wl_compositor",4);
    bind_global(shm,"wl_shm",5);
    bind_global(shell,"wl_shell",6);
    char path[]="/tmp/wayland-pattern-XXXXXX";
    int fd=mkstemp(path); unlink(path);
    if (fd<0) return 1;
    uint32_t colors[]={0xffff0000,0xff00ff00,0xff0000ff,0xffffffff};
    uint32_t row[800];
    for (int x=0;x<800;++x) row[x]=colors[x/200];
    for (int y=0;y<480;++y) if (write(fd,row,sizeof(row))!=sizeof(row)) return 1;
    request(4,0,(uint32_t[]){7},1,-1);
    request(6,0,(uint32_t[]){8,7},2,-1);
    request(8,3,NULL,0,-1);
    request(5,0,(uint32_t[]){9,800*480*4},2,fd);
    close(fd);
    request(9,0,(uint32_t[]){10,0,800,480,3200,1},6,-1);
    request(7,1,(uint32_t[]){10,0,0},3,-1);
    request(7,2,(uint32_t[]){0,0,800,480},4,-1);
    request(7,3,(uint32_t[]){11},1,-1);
    request(7,6,NULL,0,-1);
    for (;;) {
        uint32_t header[2],args[4096]; receive(header,8);
        unsigned size=header[1]>>16;
        if (size<8 || size%4 || size-8>sizeof(args)) return 1;
        receive(args,size-8);
        if (header[0]==1 && !(header[1]&65535)) {fputs("Wayland error\n",stderr);return 1;}
        if (header[0]==11 && !(header[1]&65535)) break;
    }
    puts("SOFTWARE_CLIENT_FRAME_OK"); fflush(stdout);
    sleep(2);
    return 0;
}
