/* Exercise real D-Bus mode changes and verify the rendered framebuffer. */
#include <dbus/dbus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/fb.h>

static void require(int ok, const char *message) {
    if (!ok) {fprintf(stderr,"DISPLAY_TEST_FAILED %s\n",message);exit(1);}
}
static void mode(DBusConnection *bus, const char *method, const char *signal) {
    DBusMessage *call=dbus_message_new_method_call("com.jci.lvds","/com/jci/lvds","com.jci.lvds",method);
    DBusMessageIter root, record;
    dbus_uint32_t id=8,action=0; unsigned char byte=0;
    dbus_message_iter_init_append(call,&root);
    require(dbus_message_iter_open_container(&root,DBUS_TYPE_STRUCT,NULL,&record),"open struct");
    require(dbus_message_iter_append_basic(&record,DBUS_TYPE_UINT32,&id) &&
            dbus_message_iter_append_basic(&record,DBUS_TYPE_UINT32,&action) &&
            dbus_message_iter_append_basic(&record,DBUS_TYPE_BYTE,&byte) &&
            dbus_message_iter_append_basic(&record,DBUS_TYPE_BYTE,&byte) &&
            dbus_message_iter_close_container(&root,&record),"command arguments");
    DBusError error=DBUS_ERROR_INIT;
    DBusMessage *reply=dbus_connection_send_with_reply_and_block(bus,call,3000,&error);
    require(reply!=NULL,error.message ? error.message : "method reply");
    require(dbus_message_has_signature(reply,"s"),"mode reply signature");
    dbus_message_unref(reply);dbus_message_unref(call);
    int confirmed=0;
    for (int i=0;i<30 && !confirmed;++i) {
        dbus_connection_read_write(bus,100);
        DBusMessage *message;
        while ((message=dbus_connection_pop_message(bus))) {
            if (dbus_message_is_signal(message,"com.jci.lvds",signal)) {
                dbus_int16_t value=0;
                require(dbus_message_get_args(message,NULL,DBUS_TYPE_INT16,&value,DBUS_TYPE_INVALID) && value==1,"completion signal");
                confirmed=1;
            }
            dbus_message_unref(message);
        }
    }
    require(confirmed,"completion signal timeout");
}
static void contract(DBusConnection *bus) {
    DBusError error=DBUS_ERROR_INIT;
    DBusMessage *call=dbus_message_new_method_call("com.jci.lvds","/com/jci/lvds","com.jci.lvds","SetSleepMode");
    DBusMessage *reply=dbus_connection_send_with_reply_and_block(bus,call,3000,&error);
    require(!reply && dbus_error_has_name(&error,DBUS_ERROR_INVALID_ARGS),"reject malformed mode request");
    dbus_error_free(&error);dbus_message_unref(call);
    call=dbus_message_new_method_call("com.jci.lvds","/com/jci/lvds","com.jci.lvds","GetSoftwareDispVersion");
    reply=dbus_connection_send_with_reply_and_block(bus,call,3000,&error);
    require(!reply && dbus_error_has_name(&error,DBUS_ERROR_NOT_SUPPORTED),"do not invent hardware version");
    dbus_error_free(&error);dbus_message_unref(call);
    call=dbus_message_new_method_call("com.jci.lvds","/com/jci/lvds","com.jci.lvds","GetDisplayStatus");
    dbus_uint32_t id=0;
    require(dbus_message_append_args(call,DBUS_TYPE_UINT32,&id,DBUS_TYPE_INVALID),"status arguments");
    reply=dbus_connection_send_with_reply_and_block(bus,call,3000,&error);
    require(reply && dbus_message_has_signature(reply,"u"),"status method reply");
    dbus_message_unref(reply);dbus_message_unref(call);
    int confirmed=0;
    for (int i=0;i<30 && !confirmed;++i) {
        dbus_connection_read_write(bus,100);
        DBusMessage *message;
        while ((message=dbus_connection_pop_message(bus))) {
            if (dbus_message_is_signal(message,"com.jci.lvds","DisplayStatus")) {
                require(dbus_message_has_signature(message,"(ay)"),"status signal signature");
                DBusMessageIter root,record,array;
                unsigned char *bytes;int count;
                dbus_message_iter_init(message,&root);
                dbus_message_iter_recurse(&root,&record);
                dbus_message_iter_recurse(&record,&array);
                dbus_message_iter_get_fixed_array(&array,&bytes,&count);
                require(count==17 && bytes[6]==2,"reported normal mode");
                confirmed=1;
            }
            dbus_message_unref(message);
        }
    }
    require(confirmed,"status signal timeout");
}
static void pixels(int expected_blank) {
    FILE *file=fopen("/tmp/software/frame.ppm","rb");
    require(file!=NULL,"open PPM");
    char header[32];
    require(fgets(header,sizeof(header),file)!=NULL && !strcmp(header,"P6\n"),"PPM magic");
    require(fgets(header,sizeof(header),file)!=NULL && !strcmp(header,"800 480\n"),"PPM size");
    require(fgets(header,sizeof(header),file)!=NULL && !strcmp(header,"255\n"),"PPM range");
    int lit=0;
    for (int i=0;i<800*480*3;++i) {int value=fgetc(file);require(value!=EOF,"complete PPM");lit|=value;}
    fclose(file);
    require(expected_blank ? !lit : lit,"compositor blank/visible pixels");
    int fd=open("/dev/fb0",O_RDONLY);
    struct fb_fix_screeninfo fixed;
    require(fd>=0 && !ioctl(fd,FBIOGET_FSCREENINFO,&fixed),"real framebuffer");
    unsigned int row[800];lit=0;
    for (int y=0;y<480;++y) {
        require(pread(fd,row,sizeof(row),y*fixed.line_length)==sizeof(row),"framebuffer row");
        for (int x=0;x<800;++x) lit|=row[x]&0xffffff;
    }
    close(fd);
    require(expected_blank ? !lit : lit,"VNC framebuffer blank/visible pixels");
}
int main(void) {
    DBusError error=DBUS_ERROR_INIT;
    DBusConnection *bus=dbus_connection_open_private(getenv("JCI_HMI_BUS"),&error);
    require(bus && dbus_bus_register(bus,&error),"bus registration");
    dbus_bus_add_match(bus,"type='signal',interface='com.jci.lvds'",&error);
    dbus_connection_flush(bus);
    mode(bus,"SetNormalMode","NormalModeResp");pixels(0);
    mode(bus,"SetSleepMode","SleepModeResp");pixels(1);
    mode(bus,"SetNormalMode","NormalModeResp");pixels(0);
    contract(bus);
    puts("DISPLAY_BEHAVIOR_OK: D-Bus completions, blank and restore in compositor and VNC framebuffer");
    return 0;
}
