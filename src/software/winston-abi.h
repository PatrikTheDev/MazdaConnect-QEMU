/* Recovered from CMU150 EU 74.00.324A winston 0.13.5; 32-bit ARM ABI only. */
#include <stdint.h>
#include <stddef.h>
struct wl_list { struct wl_list *prev, *next; };
struct wl_resource;
struct wl_display;
struct wl_event_loop;
struct wl_event_source;
struct output;
struct buffer {
    struct wl_list listener_link;
    void (*listener_notify)(void *, void *);
    struct wl_resource *resource;
    struct output *output;
    int refs;
};
struct plugin {
    void (*destroy)(struct plugin *);
    char *name;
    struct wl_list link;
    void *handle;
};
struct output_ops {
    int (*width)(struct output *);
    int (*height)(struct output *);
    void (*damage)(struct output *, int, int, int, int);
    void (*trigger)(struct output *);
    void (*flush)(struct output *);
    struct buffer *(*create)(struct output *, int, int, int, int);
    struct buffer *(*wrap)(struct output *, struct wl_resource *);
    void (*refresh)(struct buffer *);
    void (*load)(struct buffer *, int, int, int, int, int, int, int, const void *);
    void (*free)(struct buffer *);
    int (*buffer_width)(struct buffer *);
    int (*buffer_height)(struct buffer *);
    uint32_t (*pixel)(struct buffer *, int, int);
    int (*alpha)(struct buffer *);
    void (*read_pixels)(struct buffer *, int, int, int, int, int, void *);
    void *reserved[3];
    void *screenshot;
    void (*output_read_pixels)(struct output *, int, int, int, int, int, void *);
    int (*pending)(struct output *);
};
struct output {
    struct wl_list link, resources;
    struct wl_display *display;
    void *global;
    void (*bind)(struct wl_resource *);
    int x, y;
    struct output_ops *ops;
    int id;
    void *compositor;
};
_Static_assert(sizeof(struct buffer) == 24, "buffer ABI");
_Static_assert(sizeof(struct plugin) == 20, "plugin ABI");
_Static_assert(sizeof(struct output) == 48, "output ABI");
_Static_assert(sizeof(struct output_ops) == 84, "output ops ABI");
extern int wlxs_output_init(struct output *, void *, void (*)(struct wl_resource *));
extern void wlxs_output_fini(struct output *);
extern void wlxs_compositor_frame_update(void *, struct output *);
extern void wlxs_output_repaint(struct output *, void (*)(struct output *, void *, int, int, void *));
extern void wlxs_output_post_frames(struct output *);
extern int wlxs_view_transform_to_local(void *, int *, int *);
extern void *wl_resource_get_user_data(struct wl_resource *);
extern void wl_resource_post_event(struct wl_resource *, unsigned, ...);
extern void wl_list_remove(struct wl_list *);
extern struct wl_event_loop *wl_display_get_event_loop(struct wl_display *);
extern struct wl_event_source *wl_event_loop_add_timer(struct wl_event_loop *, int (*)(void *), void *);
extern int wl_event_source_timer_update(struct wl_event_source *, int);
extern int wl_event_source_remove(struct wl_event_source *);
