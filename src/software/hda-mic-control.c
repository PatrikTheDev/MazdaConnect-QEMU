// Lab adapter: retain HDA capture gain behavior under Mazda's mixer name.
#include <linux/module.h>
#include <linux/string.h>
#include <sound/core.h>
#include <sound/control.h>

static int rename_control(bool restore)
{
    struct snd_card *card = snd_card_ref(0);
    struct snd_ctl_elem_id source = { .iface = SNDRV_CTL_ELEM_IFACE_MIXER };
    struct snd_ctl_elem_id target = { .iface = SNDRV_CTL_ELEM_IFACE_MIXER };
    int ret;
    if (!card)
        return -ENODEV;
    if (strcmp(card->id, "CMU")) {
        snd_card_unref(card);
        return -ENODEV;
    }
    strscpy(source.name, restore ? "MIC Level Capture Volume" : "Capture Volume", sizeof(source.name));
    strscpy(target.name, restore ? "Capture Volume" : "MIC Level Capture Volume", sizeof(target.name));
    ret = snd_ctl_rename_id(card, &source, &target);
    snd_card_unref(card);
    return ret;
}

static int __init mic_init(void)
{
    int ret = rename_control(false);
    if (ret)
        pr_err("mazda_hda_mic: cannot map capture gain: %d\n", ret);
    else
        pr_info("mazda_hda_mic: CMU Capture Volume exposed as MIC Level Capture Volume; gain unchanged\n");
    return ret;
}
static void __exit mic_exit(void)
{
    int ret = rename_control(true);
    if (ret)
        pr_warn("mazda_hda_mic: cannot restore capture name: %d\n", ret);
}
module_init(mic_init);
module_exit(mic_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Mazda lab name mapping for real HDA microphone capture gain");
