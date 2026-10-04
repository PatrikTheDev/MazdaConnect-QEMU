"""Build the approved opt-in 2 GiB userspace kernel and its matching modules."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOURCE_HASH = '78cb82f50374e337d973c32ebf60d16e162589e45032db30f7a0d5295272de5e'
ROOT = Path('/software/kernels/vmsplit2g')


def build(jobs=4):
    source = Path('/usr/src/linux-source-6.1.tar.xz')
    if hashlib.file_digest(source.open('rb'),'sha256').hexdigest() != SOURCE_HASH:
        raise RuntimeError('Kernel source differs from pinned Debian 6.1.176-1 source')
    tree, output = ROOT / 'source', ROOT / 'build'
    output.mkdir(parents=True,exist_ok=True)
    (ROOT / 'manifest.json').unlink(missing_ok=True)
    if not (tree / 'Makefile').exists():
        tree.mkdir(exist_ok=True)
        subprocess.run(['tar','-xf',str(source),'-C',str(tree),'--strip-components=1'],check=True)
    config = Path('/usr/src/linux-headers-6.1.0-50-armmp/.config').read_text()
    (output / '.config').write_text(config)
    settings = tree / 'scripts/config'
    subprocess.run([str(settings),'--file',str(output / '.config'),
        '--disable','VMSPLIT_3G','--enable','VMSPLIT_2G',
        '--set-str','LOCALVERSION','-mazda-2g',
        '--set-str','MODULE_SIG_KEY','certs/signing_key.pem'],check=True)
    environment = dict(os.environ,KBUILD_BUILD_USER='mazda-qemu',
        KBUILD_BUILD_HOST='lab',KBUILD_BUILD_TIMESTAMP='Tue Sep 8 00:00:00 UTC 2026',
        KBUILD_BUILD_VERSION='1')
    command = ['make','-C',str(tree),'O='+str(output),'ARCH=arm',
               'CROSS_COMPILE=arm-linux-gnueabi-']
    subprocess.run([*command,'olddefconfig'],check=True,env=environment)
    normalized = (output / '.config').read_text()
    if 'CONFIG_VMSPLIT_2G=y\n' not in normalized or 'CONFIG_PAGE_OFFSET=0x80000000\n' not in normalized:
        raise RuntimeError('Kernel did not select the required userspace boundary')
    subprocess.run([*command,'-j'+str(jobs),'zImage','modules'],check=True,env=environment)
    version = subprocess.check_output([*command,'-s','kernelrelease'],text=True,env=environment).strip()
    package = ROOT / 'package'
    subprocess.run([*command,'INSTALL_MOD_PATH='+str(package),'modules_install'],check=True,env=environment)
    image = output / 'arch/arm/boot/zImage'
    manifest = {'profile':'vmsplit2g','version':version,'kernel':str(image),
        'headers':str(output),'package':str(package),'source_sha256':SOURCE_HASH,
        'config_sha256':hashlib.sha256(normalized.encode()).hexdigest(),
        'kernel_sha256':hashlib.file_digest(image.open('rb'),'sha256').hexdigest(),
        'config_changes':['VMSPLIT_2G instead of VMSPLIT_3G',
            'LOCALVERSION=-mazda-2g','MODULE_SIG_KEY=certs/signing_key.pem'],
        'signing':'Automatically generated lab signing key stays in the private build volume; fresh builds may differ.'}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32:
        parser.error('--jobs must be between 1 and 32')
    build(args.jobs)
