/* Software implementation of the firmware's LVDS power-control D-Bus subset. */
#include <dbus/dbus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#include "display-control.h"

#define BUS_NAME "com.jci.lvds"
#define OBJECT "/com/jci/lvds"
static int blank;

static int applied(unsigned char command, int requested) {
    int fd=socket(AF_UNIX,SOCK_SEQPACKET,0), result=-1;
    struct sockaddr_un address={.sun_family=AF_UNIX};
    strcpy(address.sun_path,DISPLAY_SOCKET);
    unsigned char request[2]={command,requested}, reply[3];
    struct pollfd wait={.fd=fd,.events=POLLIN};
    if (fd>=0 && !connect(fd,(void *)&address,sizeof(address)) &&
        send(fd,request,2,MSG_NOSIGNAL)==2 && poll(&wait,1,2000)>0 &&
        recv(fd,reply,sizeof(reply),0)==2 && reply[0]==command && reply[1]<=1 &&
        (command==DISPLAY_GET || reply[1]==requested)) {
        blank=reply[1]; result=0;
    }
    if (fd>=0) close(fd);
    return result;
}
static void send_message(DBusConnection *bus, DBusMessage *message) {
    if (!message || !dbus_connection_send(bus,message,NULL)) abort();
    dbus_message_unref(message);
}
static void error(DBusConnection *bus, DBusMessage *call, const char *name, const char *text) {
    send_message(bus,dbus_message_new_error(call,name,text));
}
static void scalar(DBusConnection *bus, DBusMessage *message, int type, const void *value) {
    if (!dbus_message_append_args(message,type,value,DBUS_TYPE_INVALID)) abort();
    send_message(bus,message);
}
static void status(DBusConnection *bus) {
    /* Vendor packet framing; VideoProxy consumes mode at byte 6 (2 normal, 1 sleep).
     * Remaining hardware fields are unspecified in this software display. */
    unsigned char bytes[17]={0x79,2,0,12,2,0,0};
    bytes[6]=blank ? 1 : 2;
    for (int i=0;i<16;++i) bytes[16]+=bytes[i];
    const unsigned char *data=bytes;
    DBusMessage *message=dbus_message_new_signal(OBJECT,BUS_NAME,"DisplayStatus");
    DBusMessageIter root, record, array;
    dbus_message_iter_init_append(message,&root);
    if (!dbus_message_iter_open_container(&root,DBUS_TYPE_STRUCT,NULL,&record) ||
        !dbus_message_iter_open_container(&record,DBUS_TYPE_ARRAY,"y",&array) ||
        !dbus_message_iter_append_fixed_array(&array,DBUS_TYPE_BYTE,&data,sizeof(bytes)) ||
        !dbus_message_iter_close_container(&record,&array) ||
        !dbus_message_iter_close_container(&root,&record)) abort();
    send_message(bus,message);
}
static DBusHandlerResult handle(DBusConnection *bus, DBusMessage *call, void *unused) {
    (void)unused;
    if (dbus_message_get_type(call)!=DBUS_MESSAGE_TYPE_METHOD_CALL) return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
    const char *method=dbus_message_get_member(call);
    fprintf(stderr,"DISPLAY_CALL %s signature=%s\n",method,dbus_message_get_signature(call));
    if (!dbus_message_has_interface(call,BUS_NAME)) {
        error(bus,call,DBUS_ERROR_UNKNOWN_INTERFACE,"Software display supports com.jci.lvds");
        return DBUS_HANDLER_RESULT_HANDLED;
    }
    const char *signal=NULL;
    int desired=-1, string_reply=0;
    if (!strcmp(method,"SetNormalMode")) {desired=0;signal="NormalModeResp";string_reply=1;}
    else if (!strcmp(method,"SetSleepMode")) {desired=1;signal="SleepModeResp";string_reply=1;}
    else if (!strcmp(method,"SetACCOff")) {desired=1;signal="ACCOffResp";}
    else if (!strcmp(method,"SetDispOn")) {desired=0;signal="DispOnResp";}
    else if (!strcmp(method,"SetDispOff")) {desired=1;signal="DispOffResp";}
    else if (!strcmp(method,"GetDisplayStatus")) {
        if (!dbus_message_has_signature(call,"u")) error(bus,call,DBUS_ERROR_INVALID_ARGS,"Expected requestId uint32");
        else if (applied(DISPLAY_GET,0)) error(bus,call,DBUS_ERROR_FAILED,"Compositor did not report its applied state");
        else {
            dbus_uint32_t accepted=0; /* Status is delivered in the following DisplayStatus signal. */
            scalar(bus,dbus_message_new_method_return(call),DBUS_TYPE_UINT32,&accepted);
            status(bus);
        }
        return DBUS_HANDLER_RESULT_HANDLED;
    }
    if (desired<0) error(bus,call,DBUS_ERROR_NOT_SUPPORTED,"Hardware-specific method is not implemented by the software display");
    else if (!dbus_message_has_signature(call,"(uuyy)")) error(bus,call,DBUS_ERROR_INVALID_ARGS,"Expected (uuyy) display command");
    else if (applied(DISPLAY_SET,desired)) error(bus,call,DBUS_ERROR_FAILED,"Compositor did not apply the requested display state");
    else {
        dbus_int16_t success=1;
        const char *text="software display state applied";
        if (string_reply) scalar(bus,dbus_message_new_method_return(call),DBUS_TYPE_STRING,&text);
        else scalar(bus,dbus_message_new_method_return(call),DBUS_TYPE_INT16,&success);
        scalar(bus,dbus_message_new_signal(OBJECT,BUS_NAME,signal),DBUS_TYPE_INT16,&success);
        fprintf(stderr,"DISPLAY_APPLIED blank=%d method=%s\n",blank,method);
    }
    return DBUS_HANDLER_RESULT_HANDLED;
}
int main(void) {
    const char *address=getenv("JCI_HMI_BUS");
    DBusError failure=DBUS_ERROR_INIT;
    if (!address || applied(DISPLAY_GET,0)) {fputs("Display compositor/bus unavailable\n",stderr);return 1;}
    DBusConnection *bus=dbus_connection_open_private(address,&failure);
    if (!bus || !dbus_bus_register(bus,&failure)) goto failed;
    if (dbus_bus_request_name(bus,BUS_NAME,DBUS_NAME_FLAG_DO_NOT_QUEUE,&failure)!=DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER) goto failed;
    DBusObjectPathVTable table={.message_function=handle};
    if (!dbus_connection_register_object_path(bus,OBJECT,&table,NULL)) goto failed;
    fputs("SOFTWARE_DISPLAY_READY\n",stderr);
    while (dbus_connection_read_write_dispatch(bus,1000)) {}
    return 1;
failed:
    fprintf(stderr,"Display D-Bus: %s\n",failure.message ? failure.message : "registration failed");
    return 1;
}
