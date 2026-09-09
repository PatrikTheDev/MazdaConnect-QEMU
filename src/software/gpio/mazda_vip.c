// SPDX-License-Identifier: GPL-2.0-only
/* Real SPI core/spidev endpoint, with explicit userspace VIP transport. */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/spi/spi.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/poll.h>
#include <linux/mutex.h>
#include <linux/sched/signal.h>
#include <linux/pid.h>
#include "vip-transport.h"

static DEFINE_MUTEX(lock);
static DECLARE_WAIT_QUEUE_HEAD(changed);
static bool connected, pending, delivered, replied;
static struct vip_packet packet;
static struct pid *irq_pid;
static struct platform_device *parent;
static struct spi_controller *controller;
static struct spi_device *device;

static int backend_open(struct inode *inode, struct file *file)
{
    int error=0;
    mutex_lock(&lock);
    if (connected) error=-EBUSY;
    else connected=true;
    mutex_unlock(&lock);
    return error;
}
static int backend_close(struct inode *inode, struct file *file)
{
    mutex_lock(&lock);
    connected=false;
    mutex_unlock(&lock);
    wake_up_all(&changed);
    return 0;
}
static ssize_t backend_read(struct file *file, char __user *buf, size_t count, loff_t *pos)
{
    int result;
    for (;;) {
        mutex_lock(&lock);
        if (pending && !delivered) break;
        mutex_unlock(&lock);
        if (file->f_flags & O_NONBLOCK) return -EAGAIN;
        result=wait_event_interruptible(changed, READ_ONCE(pending) && !READ_ONCE(delivered));
        if (result) return result;
    }
    result=VIP_HEADER_SIZE+packet.length;
    if (count < result) result=-EMSGSIZE;
    else if (copy_to_user(buf,&packet,result)) result=-EFAULT;
    else delivered=true;
    mutex_unlock(&lock);
    return result;
}
static ssize_t backend_write(struct file *file, const char __user *buf, size_t count, loff_t *pos)
{
    struct vip_packet *response;
    int result=count;
    if (count<VIP_HEADER_SIZE || count>sizeof(packet)) return -EMSGSIZE;
    response=memdup_user(buf,count);
    if (IS_ERR(response)) return PTR_ERR(response);
    mutex_lock(&lock);
    if (!pending || !delivered || replied || response->sequence!=packet.sequence) result=-ESTALE;
    else if (response->length!=packet.length || count!=VIP_HEADER_SIZE+packet.length) result=-EINVAL;
    else {
        memcpy(packet.data,response->data,packet.length);
        replied=true;
    }
    mutex_unlock(&lock);
    kfree(response);
    wake_up_all(&changed);
    return result;
}
static __poll_t backend_poll(struct file *file, poll_table *wait)
{
    __poll_t mask=0;
    poll_wait(file,&changed,wait);
    mutex_lock(&lock);
    if (pending && !delivered) mask=EPOLLIN|EPOLLRDNORM;
    mutex_unlock(&lock);
    return mask;
}
static long backend_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    int result;
    if (cmd!=VIP_RAISE_IRQ) return -ENOTTY;
    mutex_lock(&lock);
    /* This interrupt is generated only by an explicit backend event. */
    result=irq_pid ? kill_pid(irq_pid,SIGIO,1) : -ENOTCONN;
    mutex_unlock(&lock);
    return result;
}
static const struct file_operations backend_ops={
    .owner=THIS_MODULE,.open=backend_open,.release=backend_close,
    .read=backend_read,.write=backend_write,.poll=backend_poll,
    .unlocked_ioctl=backend_ioctl,.llseek=no_llseek,
};
static struct miscdevice backend={.minor=MISC_DYNAMIC_MINOR,.name="mazda_vip_transport",.fops=&backend_ops,.mode=0600};

static long cmu_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct cmu_registration registration;
    if (cmd!=CMU_REGISTER_IRQ) return -ENOTTY;
    if (copy_from_user(&registration,(void __user *)arg,sizeof(registration))) return -EFAULT;
    /* Stock VIM registers its own process and VIP interrupt GPIO 42. */
    if (registration.pid!=task_tgid_vnr(current) || registration.gpio!=42) return -EINVAL;
    mutex_lock(&lock);
    if (irq_pid && file->private_data!=irq_pid) {
        mutex_unlock(&lock);
        return -EBUSY;
    }
    if (!irq_pid) irq_pid=get_pid(task_tgid(current));
    file->private_data=irq_pid;
    mutex_unlock(&lock);
    return 0;
}
static int cmu_close(struct inode *inode, struct file *file)
{
    mutex_lock(&lock);
    if (file->private_data && file->private_data==irq_pid) {
        put_pid(irq_pid); irq_pid=NULL;
    }
    mutex_unlock(&lock);
    return 0;
}
static const struct file_operations cmu_ops={.owner=THIS_MODULE,.unlocked_ioctl=cmu_ioctl,.release=cmu_close,.llseek=no_llseek};
static struct miscdevice cmu={.minor=MISC_DYNAMIC_MINOR,.name="cmu_io",.fops=&cmu_ops,.mode=0600};

static int transfer(struct spi_controller *ctl, struct spi_device *spi, struct spi_transfer *xfer)
{
    long waited;
    int error=0;
    mutex_lock(&lock);
    if (!connected) {error=-ENOTCONN; goto out;}
    if (xfer->len>VIP_MAX_TRANSFER) {error=-EMSGSIZE; goto out;}
    packet.sequence++;
    packet.length=xfer->len;
    packet.speed_hz=xfer->speed_hz;
    packet.mode=spi->mode;
    if (xfer->tx_buf) memcpy(packet.data,xfer->tx_buf,xfer->len);
    else memset(packet.data,0,xfer->len);
    delivered=false; replied=false; pending=true;
    mutex_unlock(&lock);
    wake_up_all(&changed);
    waited=wait_event_timeout(changed, READ_ONCE(replied) || !READ_ONCE(connected), msecs_to_jiffies(2000));
    mutex_lock(&lock);
    if (!connected) error=-ENOTCONN;
    else if (!waited) error=-ETIMEDOUT;
    else if (xfer->rx_buf) memcpy(xfer->rx_buf,packet.data,xfer->len);
    pending=false;
out:
    mutex_unlock(&lock);
    return error;
}
static int __init start(void)
{
    int error;
    struct spi_board_info info={.modalias="mazda-vip",.max_speed_hz=4000000,.bus_num=1,.chip_select=0,.mode=SPI_MODE_3};
    parent=platform_device_register_simple("mazda-vip",-1,NULL,0);
    if (IS_ERR(parent)) return PTR_ERR(parent);
    controller=spi_alloc_master(&parent->dev,0);
    if (!controller) {error=-ENOMEM; goto parent_out;}
    controller->bus_num=1;
    controller->num_chipselect=1;
    controller->mode_bits=SPI_CPOL|SPI_CPHA;
    controller->bits_per_word_mask=SPI_BPW_MASK(8);
    controller->max_speed_hz=4000000;
    controller->transfer_one=transfer;
    error=spi_register_controller(controller);
    if (error) {spi_controller_put(controller); goto parent_out;}
    device=spi_new_device(controller,&info);
    if (!device) {error=-ENODEV; goto controller_out;}
    /* Explicit override uses upstream spidev without claiming an unrelated device ID. */
    error=driver_set_override(&device->dev,&device->driver_override,"spidev",7);
    if (error) goto device_out;
    error=device_attach(&device->dev);
    if (error<=0) {if (!error) error=-ENODEV; goto device_out;}
    error=misc_register(&cmu);
    if (error) goto device_out;
    error=misc_register(&backend);
    if (error) {misc_deregister(&cmu); goto device_out;}
    pr_info("MAZDA_VIP_TRANSPORT_READY: SPI1.0 and cmu_io; VIP backend required\n");
    return 0;
device_out:
    spi_unregister_device(device);
controller_out:
    spi_unregister_controller(controller);
parent_out:
    platform_device_unregister(parent);
    return error;
}
static void __exit stop(void)
{
    misc_deregister(&backend);
    misc_deregister(&cmu);
    spi_unregister_device(device);
    spi_unregister_controller(controller);
    platform_device_unregister(parent);
}
module_init(start);
module_exit(stop);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Mazda lab SPI and VIP interrupt transport for original VIM");
