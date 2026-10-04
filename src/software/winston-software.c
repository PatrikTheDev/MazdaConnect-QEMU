/* Software ARGB compositor output. No Vivante library or device dependencies. */
#include "winston-abi.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/kd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>
#include "display-control.h"

enum { WIDTH = 800, HEIGHT = 480 };
static void save_pixels(const char *, const uint32_t *);
static void trace_render(const char *stage) {
    if (!getenv("MAZDA_RENDER_TRACE")) return;
    struct timeval now;
    gettimeofday(&now,NULL);
    fprintf(stderr,"RENDER %ld.%06ld %s\n",(long)now.tv_sec,(long)now.tv_usec,stage);
}
static void display_pixels(const uint32_t *pixels) {
    static void *memory;
    static unsigned stride;
    const char *path=getenv("MAZDA_SOFTWARE_FB");
    if (!path) return;
    if (!memory) {
        int console=open("/dev/tty0",O_RDWR);
        if (console<0 || ioctl(console,KDSETMODE,KD_GRAPHICS)) {
            perror("software console graphics mode"); abort();
        }
        close(console);
        struct fb_fix_screeninfo fixed;
        struct fb_var_screeninfo variable;
        int fd=open(path,O_RDWR);
        if (fd<0 || ioctl(fd,FBIOGET_FSCREENINFO,&fixed) || ioctl(fd,FBIOGET_VSCREENINFO,&variable)) {
            perror("software framebuffer"); abort();
        }
        if (variable.xres!=WIDTH || variable.yres!=HEIGHT || variable.bits_per_pixel!=32 ||
            variable.red.offset!=16 || variable.green.offset!=8 || variable.blue.offset!=0 ||
            variable.red.length!=8 || variable.green.length!=8 || variable.blue.length!=8 ||
            variable.xoffset || variable.yoffset || fixed.line_length<WIDTH*4 ||
            fixed.smem_len<fixed.line_length*HEIGHT) {
            fprintf(stderr,"SOFTWARE unsupported framebuffer %ux%u bpp=%u stride=%u\n",
                    variable.xres,variable.yres,variable.bits_per_pixel,fixed.line_length); abort();
        }
        stride=fixed.line_length;
        memory=mmap(NULL,fixed.smem_len,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
        close(fd);
        if (memory==MAP_FAILED) {perror("software framebuffer mmap");abort();}
        fprintf(stderr,"SOFTWARE_LIVE_FB %s %ux%u\n",path,variable.xres,variable.yres);
    }
    for (int y=0;y<HEIGHT;++y)
        memcpy((char *)memory+y*stride,pixels+y*WIDTH,WIDTH*4);
}
struct pixels {
    struct buffer base;
    int width, height, format, premultiplied;
    uint32_t *data;
};
struct software {
    struct plugin plugin;
    struct output output;
    struct wl_event_source *timer;
    int pending;
    int control_fd, reply_fd, blank, control_idle;
    struct wl_event_source *control_timer;
    uint32_t frame[WIDTH * HEIGHT];
};
static struct software *owner(struct output *out) {
    return (struct software *)((char *)out - offsetof(struct software, output));
}
static int width(struct output *out) { (void)out; return WIDTH; }
static int height(struct output *out) { (void)out; return HEIGHT; }
static void trigger(struct output *out) {
    struct software *sw = owner(out);
    if (!sw->pending && sw->timer) {
        sw->pending = 1;
        trace_render("schedule");
        wl_event_source_timer_update(sw->timer, 16);
    }
}
static void damage(struct output *out, int x, int y, int w, int h) {
    (void)x; (void)y; (void)w; (void)h;
    trigger(out); /* Repaint the complete output to preserve compositing order. */
}
static int pending(struct output *out) { return owner(out)->pending; }
static struct buffer *create(struct output *out, int w, int h, int format, int premultiplied) {
    (void)out;
    if (w <= 0 || h <= 0 || w > 8192 || h > 8192 || (format != 0 && format != 1)) {
        fprintf(stderr, "SOFTWARE unsupported buffer %dx%d format=%d\n", w, h, format);
        return NULL;
    }
    struct pixels *p = calloc(1, sizeof(*p));
    if (!p) return NULL;
    p->data = calloc((size_t)w * h, 4);
    if (!p->data) { free(p); return NULL; }
    p->width = w; p->height = h; p->format = format; p->premultiplied = premultiplied;
    return &p->base;
}
static struct buffer *wrap(struct output *out, struct wl_resource *resource) {
    (void)out; (void)resource;
    fputs("SOFTWARE cannot import a non-shared-memory buffer\n", stderr);
    return NULL;
}
static void refresh(struct buffer *buffer) {
    (void)buffer;
    fputs("SOFTWARE unexpected refresh of a non-shared-memory buffer\n", stderr);
    abort();
}
static void load(struct buffer *buffer, int dx, int dy, int sx, int sy,
                 int w, int h, int stride, const void *data) {
    struct pixels *p = (struct pixels *)buffer;
    if (!data || dx < 0 || dy < 0 || sx < 0 || sy < 0 || w < 0 || h < 0 ||
        dx + w > p->width || dy + h > p->height || stride < (sx + w) * 4) {
        fputs("SOFTWARE invalid pixel upload\n", stderr); abort();
    }
    for (int y = 0; y < h; ++y)
        memcpy(p->data + (dy+y)*p->width + dx, (const char *)data + (sy+y)*stride + sx*4, (size_t)w*4);
    const char *capture = getenv("MAZDA_SOFTWARE_BUFFER");
    if (capture && p->width == WIDTH && p->height == HEIGHT)
        save_pixels(capture, p->data);
}
static void destroy_buffer(struct buffer *buffer) {
    struct pixels *p = (struct pixels *)buffer;
    if (buffer->resource) wl_list_remove(&buffer->listener_link);
    free(p->data); free(p);
}
static int buffer_width(struct buffer *b) { return ((struct pixels *)b)->width; }
static int buffer_height(struct buffer *b) { return ((struct pixels *)b)->height; }
static uint32_t pixel(struct buffer *b, int x, int y) {
    struct pixels *p = (struct pixels *)b;
    if (x < 0 || y < 0 || x >= p->width || y >= p->height) return 0;
    return p->data[y*p->width+x] | (p->format == 1 ? 0xff000000u : 0);
}
static int alpha(struct buffer *b) { return ((struct pixels *)b)->format == 0; }
static void read_pixels(struct buffer *b, int x, int y, int w, int h, int stride, void *data) {
    for (int row=0; row<h; ++row) for (int col=0; col<w; ++col)
        ((uint32_t *)((char *)data+row*stride))[col] = pixel(b,x+col,y+row);
}
static void output_read(struct output *out, int x, int y, int w, int h, int stride, void *data) {
    if (x<0 || y<0 || w<0 || h<0 || x+w>WIDTH || y+h>HEIGHT || stride<w*4) abort();
    for (int row=0; row<h; ++row)
        memcpy((char *)data+row*stride, owner(out)->frame+(y+row)*WIDTH+x, (size_t)w*4);
}
/* Recovered Winston ABI: custom-transform flag 52 and clip flag 32.
 * With custom transforms disabled,
 * update_transform installs an identity matrix plus an integer translation.
 * Ask Winston for the origin, preserving its update/rounding side effects. */
static int view_int(void *view, unsigned offset) {
    int value;
    memcpy(&value,(char *)view+offset,sizeof(value));
    return value;
}
static void draw(struct output *out, void *view, int ox, int oy, void *surface) {
    struct buffer *b = *(struct buffer **)((char *)surface + 52);
    if (!b) return;
    struct pixels *p = (struct pixels *)b;
    unsigned opacity = *(unsigned *)((char *)view + 240);
    if (!opacity) return;
    struct software *sw = owner(out);
    int bx=out->x, by=out->y;
    int translated=!getenv("MAZDA_REFERENCE_DRAW") && !view_int(view,52) && !view_int(view,32);
    if (translated) {
        (void)wlxs_view_transform_to_local(view,&bx,&by);
        /* Fall back rather than altering overflow behavior for extreme views. */
        if ((int64_t)bx+WIDTH-1>INT_MAX || (int64_t)by+HEIGHT-1>INT_MAX ||
            (int64_t)bx-ox<INT_MIN || (int64_t)bx+WIDTH-1-ox>INT_MAX ||
            (int64_t)by-oy<INT_MIN || (int64_t)by+HEIGHT-1-oy>INT_MAX)
            translated=0;
    }
    int verify=translated && getenv("MAZDA_VERIFY_DRAW");
    for (int y=0; y<HEIGHT; ++y) for (int x=0; x<WIDTH; ++x) {
        int sx,sy,inside;
        if (translated) {
            sx=bx+x; sy=by+y;
            inside=1;
            if (verify) {
                int rx=x+out->x, ry=y+out->y;
                int expected=wlxs_view_transform_to_local(view,&rx,&ry);
                if (inside!=expected || sx!=rx || sy!=ry) {
                    fprintf(stderr,"SOFTWARE_DRAW_MISMATCH at %d,%d local %d,%d/%d reference %d,%d/%d\n",
                            x,y,sx,sy,inside,rx,ry,expected);
                    abort();
                }
            }
        } else {
            sx=x+out->x; sy=y+out->y;
            inside=wlxs_view_transform_to_local(view,&sx,&sy);
        }
        if (!inside) continue;
        sx-=ox; sy-=oy;
        if (sx<0 || sy<0 || sx>=p->width || sy>=p->height) continue;
        uint32_t src=pixel(b,sx,sy), dst=sw->frame[y*WIDTH+x];
        unsigned a=(src>>24)*opacity/255, result=0xff000000u;
        for (unsigned shift=0; shift<24; shift+=8) {
            unsigned channel=(src>>shift)&255;
            unsigned scaled=channel*(p->premultiplied ? opacity : a)/255;
            unsigned blended=scaled+(((dst>>shift)&255)*(255-a)+127)/255;
            result |= (blended>255 ? 255 : blended)<<shift;
        }
        sw->frame[y*WIDTH+x]=result;
    }
    if (verify) fprintf(stderr,"SOFTWARE_DRAW_VERIFIED pixels=%d offset=%d,%d\n",
                        WIDTH*HEIGHT,bx,by);
}
static void save_pixels(const char *path, const uint32_t *pixels) {
    char *temporary=malloc(strlen(path)+5);
    if (!temporary) return;
    sprintf(temporary,"%s.tmp",path);
    FILE *file=fopen(temporary,"wb");
    if (!file) { perror("software frame"); free(temporary); return; }
    int complete=1;
    fprintf(file,"P6\n%d %d\n255\n",WIDTH,HEIGHT);
    unsigned char *rgb = malloc(WIDTH*HEIGHT*3);
    if (!rgb) { fclose(file); remove(temporary); free(temporary); return; }
    trace_render("convert_begin");
    for (int y=0; y<HEIGHT; ++y) {
        for (int x=0; x<WIDTH; ++x) {
            uint32_t c=pixels[y*WIDTH+x];
            size_t offset = ((size_t)y*WIDTH+x)*3;
            rgb[offset]=c>>16; rgb[offset+1]=c>>8; rgb[offset+2]=c;
        }
    }
    trace_render("converted");
    if (fwrite(rgb,1,WIDTH*HEIGHT*3,file)!=WIDTH*HEIGHT*3) { perror("software frame write"); complete=0; }
    trace_render("written");
    free(rgb);
    if (fclose(file)) complete=0;
    /* Readers must never capture a partially written frame. */
    if (complete && rename(temporary,path)) perror("software frame rename");
    remove(temporary);
    free(temporary);
}
static int repaint(void *data) {
    struct software *sw=data;
    sw->pending=0;
    trace_render("begin");
    wlxs_compositor_frame_update(sw->output.compositor,&sw->output);
    trace_render("updated");
    memset(sw->frame,0,sizeof(sw->frame));
    wlxs_output_repaint(&sw->output,draw);
    trace_render("painted");
    if (sw->blank) memset(sw->frame,0,sizeof(sw->frame));
    display_pixels(sw->frame);
    trace_render("displayed");
    const char *path=getenv("MAZDA_SOFTWARE_FRAME");
    save_pixels(path ? path : "/tmp/software-frame.ppm",sw->frame);
    trace_render("saved");
    wlxs_output_post_frames(&sw->output);
    trace_render("callbacks");
    return 0;
}
/* Poll separately from repaint: blank/unblank must work with an idle client. */
static int control_tick(void *data) {
    struct software *sw=data;
    if (sw->reply_fd < 0) {
        sw->reply_fd=accept(sw->control_fd,NULL,NULL);
        sw->control_idle=0;
    }
    if (sw->reply_fd >= 0) {
        unsigned char request[3];
        int n=recv(sw->reply_fd,request,sizeof(request),MSG_DONTWAIT);
        if (n==2 && request[0]==DISPLAY_SET && request[1]<=1) {
            sw->blank=request[1];
            /* Complete synchronously so the reply describes pixels already applied. */
            repaint(sw);
            unsigned char reply[2]={DISPLAY_SET,sw->blank};
            send(sw->reply_fd,reply,sizeof(reply),MSG_NOSIGNAL);
            close(sw->reply_fd); sw->reply_fd=-1;
        } else if (n==2 && request[0]==DISPLAY_GET) {
            unsigned char reply[2]={DISPLAY_GET,sw->blank};
            send(sw->reply_fd,reply,sizeof(reply),MSG_NOSIGNAL);
            close(sw->reply_fd); sw->reply_fd=-1;
        } else if (n>=0 || ++sw->control_idle>100) {
            close(sw->reply_fd); sw->reply_fd=-1;
        }
    }
    wl_event_source_timer_update(sw->control_timer,20);
    return 0;
}
static void bind_output(struct wl_resource *resource) {
    struct output *out=wl_resource_get_user_data(resource);
    wl_resource_post_event(resource,0,out->x,out->y,200,120,0,"Lab","Software",0);
    wl_resource_post_event(resource,1,3,WIDTH,HEIGHT,60000);
}
static struct output_ops ops={
    .width=width,.height=height,.damage=damage,.trigger=trigger,.flush=trigger,
    .create=create,.wrap=wrap,.refresh=refresh,.load=load,.free=destroy_buffer,
    .buffer_width=buffer_width,.buffer_height=buffer_height,.pixel=pixel,.alpha=alpha,
    .read_pixels=read_pixels,.output_read_pixels=output_read,.pending=pending
};
static void destroy_plugin(struct plugin *plugin) {
    struct software *sw=(struct software *)plugin;
    if (sw->control_timer) wl_event_source_remove(sw->control_timer);
    if (sw->reply_fd>=0) close(sw->reply_fd);
    close(sw->control_fd); unlink(DISPLAY_SOCKET);
    if (sw->timer) wl_event_source_remove(sw->timer);
    wlxs_output_fini(&sw->output);
    free(sw);
}
struct {const char *version,*description; const char **help;} wlxs_software_plugin_info={
    "0.13.5 141205","CPU shared-memory output for the Mazda QEMU lab",NULL
};
struct plugin *wlxs_software_plugin_init(void *compositor,void *config) {
    (void)config;
    struct software *sw=calloc(1,sizeof(*sw));
    if (!sw) return NULL;
    sw->reply_fd=-1;
    sw->control_fd=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_NONBLOCK,0);
    struct sockaddr_un address={.sun_family=AF_UNIX};
    strcpy(address.sun_path,DISPLAY_SOCKET);
    if (sw->control_fd<0 || bind(sw->control_fd,(void *)&address,sizeof(address)) || listen(sw->control_fd,4)) {
        perror("software display control"); abort();
    }
    sw->plugin.destroy=destroy_plugin;
    sw->output.ops=&ops;
    if (!wlxs_output_init(&sw->output,compositor,bind_output)) {free(sw);return NULL;}
    sw->timer=wl_event_loop_add_timer(wl_display_get_event_loop(sw->output.display),repaint,sw);
    if (!sw->timer) {wlxs_output_fini(&sw->output);free(sw);return NULL;}
    sw->control_timer=wl_event_loop_add_timer(wl_display_get_event_loop(sw->output.display),control_tick,sw);
    if (!sw->control_timer) abort();
    wl_event_source_timer_update(sw->control_timer,20);
    trigger(&sw->output);
    fputs("SOFTWARE_OUTPUT_READY 800x480\n",stderr);
    return &sw->plugin;
}
