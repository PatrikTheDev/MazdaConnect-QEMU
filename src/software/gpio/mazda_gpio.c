// SPDX-License-Identifier: GPL-2.0-only
/* QEMU lab GPIO bank: stateful lines and real gpiolib sysfs edge notifications. */
#include <linux/module.h>
#include <linux/gpio.h>
#include <linux/gpio/driver.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/machine.h>
#include <linux/irq.h>
#include <linux/irqdesc.h>
#include <linux/interrupt.h>
#include <linux/thermal.h>
#include <linux/platform_device.h>

enum { IGNITION, ACC, SHUTDOWN, REVERSE, HOLD, RESET, NORMAL, READY, EMERGENCY, MIC_EN, CAM_EN, BOOT_FAIL, MIC_GOOD, CAM_GOOD, USB_GOOD, USB_EN, INHIBIT, DAY, LINES };
static const char *const names[LINES] = {
    "CAN_Ignition_Status", "ACC_Sense", "Safe_Shutdown", "Reverse",
    "Power Hold", "Reset VIP", "MAP_Normal_Mode", "MAP_Powerdown_Ready", "Emergency", "DO_MIC_PWR_EN",
    "DO_CAM_PWR_EN", "DO_MAP_BOOT_FAIL", "Mic Power Good", "Camera Power Good",
    "USB Power Good", "DO_USB_PWR_EN", "CAN Inhibit Sense", "CAN_Day_Mode"
};
static int values[LINES] = {[IGNITION]=1, [ACC]=1, [REVERSE]=1, [RESET]=1, [DAY]=1};
static int directions[LINES] = {[IGNITION]=1, [ACC]=1, [SHUTDOWN]=1, [REVERSE]=1, [MIC_GOOD]=1, [CAM_GOOD]=1, [USB_GOOD]=1, [INHIBIT]=1, [DAY]=1};
static unsigned int edges[LINES];
static bool masked[LINES];
static int irq_base = -1;
static struct gpio_chip bank;
static struct platform_device *platform;
static struct device *vim_device;
static struct device *line_devices[LINES];
/* Exported GPIO class devices are descendants of our own platform parent. */
struct device_search { const char *name; struct device *found; };
static int match_name(struct device *dev, void *data)
{
    struct device_search *search = data;
    return !strcmp(dev_name(dev), search->name);
}
static int find_descendant(struct device *dev, void *data)
{
    struct device_search *search = data;
    search->found = device_find_child(dev, search, match_name);
    return search->found ? 1 : device_for_each_child(dev, data, find_descendant);
}
static struct device *find_line(const char *name)
{
    struct device_search search = {name, NULL};
    find_descendant(&platform->dev, &search);
    return search.found;
}
static struct gpio_desc *descriptors[LINES];

static void line_mask(struct irq_data *d) { WRITE_ONCE(masked[d->irq-irq_base], true); }
static void line_unmask(struct irq_data *d) { WRITE_ONCE(masked[d->irq-irq_base], false); }
static int line_type(struct irq_data *d, unsigned int type)
{
    if (type & ~IRQ_TYPE_EDGE_BOTH) return -EINVAL;
    WRITE_ONCE(edges[d->irq-irq_base], type);
    return 0;
}
static struct irq_chip interrupts = {
    .name = "mazda-lab-gpio", .irq_mask = line_mask,
    .irq_unmask = line_unmask, .irq_set_type = line_type,
};
static int get(struct gpio_chip *chip, unsigned int line) { return READ_ONCE(values[line]); }
static void set(struct gpio_chip *chip, unsigned int line, int value)
{
    int old = READ_ONCE(values[line]);
    WRITE_ONCE(values[line], !!value);
    /* Original VIM polls output values without configuring an input IRQ. */
    if (old != !!value && !READ_ONCE(directions[line]) && line_devices[line])
        sysfs_notify(&line_devices[line]->kobj, NULL, "value");
}
static int direction(struct gpio_chip *chip, unsigned int line) { return READ_ONCE(directions[line]); }
static int input(struct gpio_chip *chip, unsigned int line) { WRITE_ONCE(directions[line], 1); return 0; }
static int output(struct gpio_chip *chip, unsigned int line, int value)
{
    set(chip, line, value);
    WRITE_ONCE(directions[line], 0);
    return 0;
}
static int to_irq(struct gpio_chip *chip, unsigned int line) { return irq_base + line; }

/* Change physical input levels through /sys/module/mazda_gpio/parameters/NAME.
 * gpiolib owns direction, polarity, edge selection, and poll(POLLPRI) delivery.
 */
static int inject(const char *text, const struct kernel_param *param)
{
    int line = (int *)param->arg - values;
    bool value;
    int old, error = kstrtobool(text, &value);
    unsigned int edge;
    if (error) return error;
    if (irq_base >= 0 && !READ_ONCE(directions[line])) return -EPERM;
    old = READ_ONCE(values[line]);
    WRITE_ONCE(values[line], value);
    edge = value ? IRQ_TYPE_EDGE_RISING : IRQ_TYPE_EDGE_FALLING;
    if (irq_base >= 0 && old != value && !READ_ONCE(masked[line]) &&
        (READ_ONCE(edges[line]) & edge))
        generic_handle_irq_safe(irq_base + line);
    return 0;
}
static const struct kernel_param_ops input_ops = {.set = inject, .get = param_get_int};
module_param_cb(ignition, &input_ops, &values[IGNITION], 0600);
module_param_cb(acc, &input_ops, &values[ACC], 0600);
module_param_cb(safe_shutdown, &input_ops, &values[SHUTDOWN], 0600);
module_param_cb(reverse, &input_ops, &values[REVERSE], 0600);
MODULE_PARM_DESC(ignition, "Simulated CAN_Ignition_Status input level (0/1)");
MODULE_PARM_DESC(acc, "Simulated ACC_Sense input level (0/1)");
MODULE_PARM_DESC(safe_shutdown, "Simulated Safe_Shutdown input level (0/1)");
MODULE_PARM_DESC(reverse, "Simulated Reverse input level (0/1)");

/* VIM forwards VIP GPIO updates as exact "name,0\n" / "name,1\n" commands. */
static ssize_t vim_store(struct device *dev, struct device_attribute *attr,
                         const char *buf, size_t count)
{
    int i, old, value;
    size_t length = count;
    if (length && buf[length-1]=='\n') length--;
    if (length < 3 || buf[length-2]!=',' || (buf[length-1]!='0' && buf[length-1]!='1'))
        return -EINVAL;
    for (i=0; i<LINES; i++)
        if (strlen(names[i])==length-2 && !memcmp(buf,names[i],length-2)) break;
    if (i==LINES) return -ENOENT;
    /* Only names observed in GPIOMON_ProcessEvent are accepted. */
    if (i!=MIC_GOOD && i!=CAM_GOOD && i!=USB_GOOD && i!=REVERSE && i!=USB_EN &&
        i!=INHIBIT && i!=DAY && i!=SHUTDOWN && i!=IGNITION) return -EPERM;
    value=buf[length-1]-'0'; old=READ_ONCE(values[i]);
    set(&bank,i,value);
    if (old!=value && !READ_ONCE(masked[i]) &&
        (READ_ONCE(edges[i]) & (value ? IRQ_TYPE_EDGE_RISING : IRQ_TYPE_EDGE_FALLING)))
        generic_handle_irq_safe(irq_base+i);
    return count;
}
static DEVICE_ATTR_WO(vim);
static void release_devices(void)
{
    int i;
    if (vim_device) {
        device_remove_file(vim_device, &dev_attr_vim);
        put_device(vim_device); vim_device=NULL;
    }
    for (i=0; i<LINES; i++) {
        if (line_devices[i]) put_device(line_devices[i]);
        line_devices[i]=NULL;
    }
}

/* Lab temperatures are millidegrees Celsius, matching Linux thermal sysfs.
 * The trip is fixed for a module lifetime because the firmware caches it at boot.
 * A passive trip leaves shutdown decisions to the original firmware service.
 */
static int temperature = 25000;
static int trip_temperature = 95000;
static struct thermal_zone_device *sensor;
static int set_temperature(const char *text, const struct kernel_param *param)
{
    int value, error = kstrtoint(text, 0, &value);
    if (error) return error;
    if (value < -40000 || value > 150000) return -ERANGE;
    WRITE_ONCE(*(int *)param->arg, value);
    return 0;
}
static const struct kernel_param_ops temperature_ops = {
    .set = set_temperature, .get = param_get_int,
};
module_param_cb(temperature, &temperature_ops, &temperature, 0600);
module_param_cb(trip_temperature, &temperature_ops, &trip_temperature, 0444);
MODULE_PARM_DESC(temperature, "Simulated temperature in millidegrees Celsius (-40000..150000)");
MODULE_PARM_DESC(trip_temperature, "Boot-time firmware trip threshold in millidegrees Celsius (default 95000; lab value)");
static int sensor_get(struct thermal_zone_device *zone, int *value)
{
    *value = READ_ONCE(temperature);
    return 0;
}
static int sensor_trip(struct thermal_zone_device *zone, int trip, int *value)
{
    if (trip != 0) return -EINVAL;
    *value = trip_temperature;
    return 0;
}
static int sensor_type(struct thermal_zone_device *zone, int trip, enum thermal_trip_type *type)
{
    if (trip != 0) return -EINVAL;
    *type = THERMAL_TRIP_PASSIVE;
    return 0;
}
static struct thermal_zone_device_ops sensor_ops = {
    .get_temp = sensor_get, .get_trip_temp = sensor_trip, .get_trip_type = sensor_type,
};

static void release_irqs(void)
{
    int i;
    for (i = 0; i < LINES; i++) {
        irq_set_chip_and_handler(irq_base+i, NULL, NULL);
        irq_set_status_flags(irq_base+i, IRQ_NOREQUEST);
    }
    irq_free_descs(irq_base, LINES);
    irq_base = -1;
}
static int __init start(void)
{
    int i, error;
    platform=platform_device_register_simple("mazda-signals", -1, NULL, 0);
    if (IS_ERR(platform)) return PTR_ERR(platform);
    irq_base = irq_alloc_descs(-1, 0, LINES, NUMA_NO_NODE);
    if (irq_base < 0) {error=irq_base; goto parent;}
    for (i = 0; i < LINES; i++) {
        masked[i] = true;
        irq_set_chip_and_handler(irq_base+i, &interrupts, handle_simple_irq);
        irq_clear_status_flags(irq_base+i, IRQ_NOREQUEST);
    }
    bank = (struct gpio_chip) {
        .label = "mazda-qemu-signals", .owner = THIS_MODULE, .base = 224,
        .parent = &platform->dev, .can_sleep = true,
        .ngpio = LINES, .names = names, .get = get, .set = set,
        .get_direction = direction, .direction_input = input,
        .direction_output = output, .to_irq = to_irq,
    };
    error = gpiochip_add_data(&bank, NULL);
    if (error) goto irqs;
    for (i = 0; i < LINES; i++) {
        enum gpiod_flags flags = directions[i] ? GPIOD_IN :
            (values[i] ? GPIOD_OUT_HIGH : GPIOD_OUT_LOW);
        descriptors[i] = gpiochip_request_own_desc(&bank, i, names[i], GPIO_ACTIVE_HIGH, flags);
        if (IS_ERR(descriptors[i])) { error=PTR_ERR(descriptors[i]); goto lines; }
        error = gpiod_export(descriptors[i], true);
        if (error) { gpiochip_free_own_desc(descriptors[i]); goto lines; }
    }
    for (i=0; i<LINES; i++) {
        line_devices[i]=find_line(names[i]);
        if (!line_devices[i]) {error=-ENODEV; i=LINES; goto lines;}
    }
    vim_device=find_line("gpiochip224");
    if (!vim_device) {error=-ENODEV; goto lines;}
    error=device_create_file(vim_device, &dev_attr_vim);
    if (error) goto lines;
    sensor = thermal_zone_device_register("mazda-lab", 1, 0, NULL, &sensor_ops, NULL, 0, 0);
    if (IS_ERR(sensor)) { error=PTR_ERR(sensor); goto lines; }
    if (sensor->id != 0) {
        pr_err("mazda lab requires thermal_zone0; another sensor already owns it\n");
        thermal_zone_device_unregister(sensor);
        error=-EBUSY; goto lines;
    }
    pr_info("MAZDA_THERMAL_READY: temp=%d trip=%d millidegrees Celsius\n", temperature, trip_temperature);
    pr_info("MAZDA_GPIO_READY: stateful ignition/power GPIOs exported\n");
    return 0;
lines:
    release_devices();
    while (i--) gpiochip_free_own_desc(descriptors[i]);
    gpiochip_remove(&bank);
irqs:
    release_irqs();
parent:
    platform_device_unregister(platform);
    return error;
}
static void __exit stop(void)
{
    int i;
    thermal_zone_device_unregister(sensor);
    release_devices();
    for (i = 0; i < LINES; i++) gpiochip_free_own_desc(descriptors[i]);
    gpiochip_remove(&bank);
    release_irqs();
    platform_device_unregister(platform);
}
module_init(start);
module_exit(stop);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Mazda QEMU lab power and ignition GPIO simulation");
