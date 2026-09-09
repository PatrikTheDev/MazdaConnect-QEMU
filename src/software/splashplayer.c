/* Lab replacement for the VPU splash player: real VP8 decoding and wl_shm output. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>
#include <vpx/vpx_decoder.h>
#include <vpx/vp8dx.h>
#include "wayland-wire.h"

enum { WIDTH=800, HEIGHT=480, FRAME_BYTES=WIDTH*HEIGHT*4 };
static volatile sig_atomic_t stopping;
static int busy[2], frame_done;
static uint32_t callback;
static const char *pidfile;
static void stop(int sig) { (void)sig; stopping=1; wire_stopping=1; }
static void cleanup(void) { if (pidfile) unlink(pidfile); }
static uint32_t le32(const unsigned char *p) {
    return p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static uint64_t now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;
}
static void event(void) {
    uint32_t h[2],a[4096]; receive(h,8);
    unsigned size=h[1]>>16;
    if (size<8 || size%4 || size-8>sizeof(a)) exit(1);
    receive(a,size-8);
    if (h[0]==1 && !(h[1]&65535)) {fputs("PLAYER Wayland protocol error\n",stderr);exit(1);}
    if (h[0]==callback && !(h[1]&65535)) frame_done=1;
    if ((h[0]==11 || h[0]==12) && !(h[1]&65535)) busy[h[0]-11]=0;
}
static void scalar(const char *title,int property,int value) {
    uint32_t args[128]={strlen(title)+1};
    unsigned words=(args[0]+3)/4;
    if (words>110) exit(2);
    memcpy(args+1,title,args[0]);
    args[words+1]=property;
    args[words+4]=value*256;
    request(9,5,args,words+7,-1);
}
static uint8_t clamp(int n) {return n<0?0:n>255?255:n;}
static void convert(const vpx_image_t *image,uint32_t *pixels) {
    if (image->fmt!=VPX_IMG_FMT_I420 || image->d_w!=WIDTH || image->d_h!=HEIGHT) {
        fputs("PLAYER unsupported decoded pixel format or size\n",stderr);exit(1);
    }
    for (int y=0;y<HEIGHT;++y) for (int x=0;x<WIDTH;++x) {
        int yy=image->planes[0][y*image->stride[0]+x];
        int u=image->planes[1][(y/2)*image->stride[1]+x/2]-128;
        int v=image->planes[2][(y/2)*image->stride[2]+x/2]-128;
        int c=yy-16;
        unsigned r=clamp((298*c+409*v+128)>>8);
        unsigned g=clamp((298*c-100*u-208*v+128)>>8);
        unsigned b=clamp((298*c+516*u+128)>>8);
        pixels[y*WIDTH+x]=0xff000000u|r<<16|g<<8|b;
    }
}
int main(int argc,char **argv) {
    const char *title="splashplayer";
    int quit=0,loop=0,zorder=1,option;
    while ((option=getopt(argc,argv,"qlp:t:z:"))!=-1) {
        switch (option) {
        case 'q':quit=1;break;
        case 'l':loop=1;break;
        case 'p':pidfile=optarg;break;
        case 't':title=optarg;break;
        case 'z':zorder=atoi(optarg);break;
        default:return 2;
        }
    }
    if (optind+1!=argc || strlen(title)>128 || zorder<0 || zorder>32767) return 2;
    FILE *movie=fopen(argv[optind],"rb");
    unsigned char header[32];
    if (!movie || fread(header,1,32,movie)!=32 || memcmp(header,"DKIF\0\0\x20\0VP80",12) ||
        (header[12]|header[13]<<8)!=WIDTH || (header[14]|header[15]<<8)!=HEIGHT) {
        fputs("PLAYER requires an 800x480 VP8 IVF file\n",stderr);return 1;
    }
    uint32_t rate=le32(header+16),scale=le32(header+20);
    if (!rate || !scale || scale>rate) return 1;
    signal(SIGTERM,stop);signal(SIGINT,stop);atexit(cleanup);
    alarm(90);
    sock=socket(AF_UNIX,SOCK_STREAM,0);
    struct sockaddr_un addr={.sun_family=AF_UNIX};
    const char *runtime=getenv("XDG_RUNTIME_DIR");
    if (!runtime) runtime="/tmp/lab-wayland";
    if (snprintf(addr.sun_path,sizeof(addr.sun_path),"%s/wayland-0",runtime)>=(int)sizeof(addr.sun_path)) return 2;
    if (connect(sock,(void *)&addr,sizeof(addr))) {perror("PLAYER connect");return 1;}
    request(1,1,(uint32_t[]){2},1,-1);request(1,0,(uint32_t[]){3},1,-1);
    uint32_t comp=0,shm=0,ivi=0,shell=0;
    for (;;) {
        uint32_t h[2],a[4096]; receive(h,8);
        unsigned size=h[1]>>16;
        if (size<8 || size%4 || size-8>sizeof(a)) return 1;
        receive(a,size-8);
        if (h[0]==2 && !(h[1]&65535)) {
            if (size<20 || !a[1] || a[1]>size-20 || ((char *)(a+2))[a[1]-1]) return 1;
            const char *name=(char *)(a+2);
            if (!strcmp(name,"wl_compositor")) comp=a[0];
            if (!strcmp(name,"wl_shm")) shm=a[0];
            if (!strcmp(name,"wl_ivi")) ivi=a[0];
            if (!strcmp(name,"wl_ivi_shell")) shell=a[0];
        }
        if (h[0]==3 && !(h[1]&65535)) break;
    }
    if (!comp || !shm || !ivi || !shell) return 1;
    bind_global(comp,"wl_compositor",4);bind_global(shm,"wl_shm",5);
    bind_global(ivi,"wl_ivi",6);bind_global(shell,"wl_ivi_shell",7);
    request(4,0,(uint32_t[]){8},1,-1);
    uint32_t registration[64]={8,strlen(title)+1};
    memcpy(registration+2,title,registration[1]);
    request(6,0,registration,2+(registration[1]+3)/4,-1);
    request(7,0,(uint32_t[]){9},1,-1);
    scalar(title,1,zorder);scalar(title,2,255);
    request(9,0,NULL,0,-1);request(9,3,NULL,0,-1);
    char path[]="/tmp/software-video-XXXXXX";
    int fd=mkstemp(path);unlink(path);
    if (fd<0 || ftruncate(fd,2*FRAME_BYTES)) return 1;
    uint32_t *pixels=mmap(NULL,2*FRAME_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if (pixels==MAP_FAILED) return 1;
    request(5,0,(uint32_t[]){10,2*FRAME_BYTES},2,fd);close(fd);
    request(10,0,(uint32_t[]){11,0,WIDTH,HEIGHT,WIDTH*4,1},6,-1);
    request(10,0,(uint32_t[]){12,FRAME_BYTES,WIDTH,HEIGHT,WIDTH*4,1},6,-1);
    vpx_codec_ctx_t decoder;
    vpx_codec_dec_cfg_t config={.threads=1,.w=WIDTH,.h=HEIGHT};
    uint32_t next=13;
    unsigned decoded=0,presented=0;
    int ready=0,index=0;
    do {
        if (vpx_codec_dec_init(&decoder,vpx_codec_vp8_dx(),&config,0)) return 1;
        fseek(movie,32,SEEK_SET);
        uint64_t start=now(),last_pts=0,last_present=0;
        while (!stopping) {
            unsigned char fh[12];
            size_t got=fread(fh,1,12,movie);
            if (!got) break;
            if (got!=12) return 1;
            uint32_t size=le32(fh);
            uint64_t pts=le32(fh+4)|(uint64_t)le32(fh+8)<<32;
            if (!size || size>16*1024*1024 || pts<last_pts || pts>UINT64_MAX/1000000000/scale) return 1;
            last_pts=pts;
            unsigned char *frame=malloc(size);
            if (!frame || fread(frame,1,size,movie)!=size) return 1;
            int error=vpx_codec_decode(&decoder,frame,size,NULL,0);free(frame);
            if (error) {fprintf(stderr,"PLAYER decode: %s\n",vpx_codec_error(&decoder));return 1;}
            decoded++;
            uint64_t due=start+pts*1000000000*scale/rate;
            vpx_codec_iter_t iter=NULL;
            vpx_image_t *image=vpx_codec_get_frame(&decoder,&iter);
            if (!image) continue;
            /* Decode every interdependent frame; omit overdue presentations. */
            if (ready && now()>due+100000000 && now()-last_present<125000000) continue;
            while (now()<due && !stopping) {
                struct timespec delay={0,1000000}; nanosleep(&delay,NULL);
            }
            while (busy[index] && !stopping) event();
            if (stopping) break;
            convert(image,pixels+index*WIDTH*HEIGHT);
            callback=next++;frame_done=0;busy[index]=1;
            request(8,1,(uint32_t[]){11+index,0,0},3,-1);
            request(8,2,(uint32_t[]){0,0,WIDTH,HEIGHT},4,-1);
            request(8,3,&callback,1,-1);request(8,6,NULL,0,-1);
            while (!frame_done && !stopping) event();
            presented++;index^=1;last_present=now();
            if (!ready) {
                if (pidfile) {
                    FILE *pid=fopen(pidfile,"w");
                    if (!pid) {perror("PLAYER pidfile");return 1;}
                    fprintf(pid,"%d\n",getpid());fclose(pid);
                }
                ready=1;alarm(0);fprintf(stderr,"SOFTWARE_VIDEO_READY %s\n",title);
            }
        }
        vpx_codec_destroy(&decoder);
    } while (loop && !stopping);
    fprintf(stderr,"SOFTWARE_VIDEO_DONE decoded=%u presented=%u\n",decoded,presented);
    if (!decoded || !presented) return 1;
    if (!quit && !stopping) {alarm(0);while (!stopping) pause();}
    munmap(pixels,2*FRAME_BYTES);fclose(movie);close(sock);
    return 0;
}
