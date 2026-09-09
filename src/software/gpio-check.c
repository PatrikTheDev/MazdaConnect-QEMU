/* Verify actual GPIO sysfs values and poll notifications before starting services. */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void put(const char *path,const char *value) {
    int fd=open(path,O_WRONLY);
    if (fd<0 || write(fd,value,strlen(value))!=(ssize_t)strlen(value)) {perror(path);exit(1);}
    close(fd);
}
static void expect_value(int fd,int value) {
    char data[8]={0};
    if (lseek(fd,0,SEEK_SET)<0 || read(fd,data,sizeof(data)-1)<1 || atoi(data)!=value) {
        fputs("GPIO value mismatch\n",stderr);exit(1);
    }
}
static void edge(int fd,int expected) {
    struct pollfd p={.fd=fd,.events=POLLPRI|POLLERR};
    int result=poll(&p,1,expected?1000:30);
    if (result<0 || (expected ? !(p.revents&POLLPRI) : result!=0)) {
        fprintf(stderr,"GPIO edge mismatch: result=%d revents=%x\n",result,p.revents);exit(1);
    }
}
int main(void) {
    const char *input="/sys/module/mazda_gpio/parameters/reverse";
    alarm(10);
    const char *thermal="/sys/devices/virtual/thermal/thermal_zone0/temp";
    int sensor=open(thermal,O_RDONLY);
    if (sensor<0) {perror(thermal);return 1;}
    expect_value(sensor,25000);
    put("/sys/module/mazda_gpio/parameters/temperature","42000");
    expect_value(sensor,42000);
    int parameter=open("/sys/module/mazda_gpio/parameters/temperature",O_WRONLY);
    if (parameter<0 || write(parameter,"150001",6)!=-1) {fputs("Invalid temperature accepted\n",stderr);return 1;}
    close(parameter);expect_value(sensor,42000);
    put("/sys/module/mazda_gpio/parameters/temperature","25000");
    expect_value(sensor,25000);close(sensor);
    sensor=open("/sys/devices/virtual/thermal/thermal_zone0/trip_point_0_temp",O_RDONLY);
    if (sensor<0) return 1;
    expect_value(sensor,95000);close(sensor);
    puts("THERMAL_BEHAVIOR_OK: readable temperature, configurable value, bounds and trip threshold");
    put("/sys/class/gpio/Reverse/direction","in");
    put("/sys/class/gpio/Reverse/edge","rising");
    int fd=open("/sys/class/gpio/Reverse/value",O_RDONLY|O_NONBLOCK);
    if (fd<0) {perror("GPIO open");return 1;}
    expect_value(fd,1); /* Active-low reverse starts disengaged. */
    put(input,"0");expect_value(fd,0);
    put(input,"1");edge(fd,1);expect_value(fd,1);
    put(input,"1");edge(fd,0);expect_value(fd,1);
    put(input,"0");edge(fd,0);expect_value(fd,0);
    put("/sys/class/gpio/Reverse/edge","both");
    expect_value(fd,0);
    put(input,"1");edge(fd,1);expect_value(fd,1);
    put(input,"0");edge(fd,1);expect_value(fd,0);
    put("/sys/class/gpio/gpiochip224/vim","Reverse,1\n");edge(fd,1);expect_value(fd,1);
    put("/sys/class/gpio/gpiochip224/vim","Reverse,1\n");edge(fd,0);
    int vim=open("/sys/class/gpio/gpiochip224/vim",O_WRONLY);
    const char *invalid[]={"Reverse,2\n","Missing,1\n","Power Hold,1\n","Reverse,0\nextra"};
    if (vim<0) return 1;
    for (unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++) {
        if (write(vim,invalid[i],strlen(invalid[i]))!=-1) {
            fputs("Invalid VIM command accepted\n",stderr);return 1;
        }
        expect_value(fd,1);edge(fd,0);
    }
    close(vim);
    put("/sys/class/gpio/Reverse/edge","none");
    put(input,"1");expect_value(fd,1); /* Restore the simulated parked state. */
    close(fd);
    put("/sys/class/gpio/Power Hold/direction","out");
    put("/sys/class/gpio/Power Hold/value","1");
    fd=open("/sys/class/gpio/Power Hold/value",O_RDONLY);
    if (fd<0) return 1;
    expect_value(fd,1);
    put("/sys/class/gpio/Power Hold/value","0");edge(fd,1);expect_value(fd,0);
    put("/sys/class/gpio/Power Hold/value","0");edge(fd,0);
    close(fd);
    puts("VIM_GPIO_BEHAVIOR_OK: command updates, rejected invalid commands, output notifications");
    puts("GPIO_BEHAVIOR_OK: values, rising/both edges, unchanged levels and output writes");
    return 0;
}
