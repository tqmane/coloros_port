<div align="center">

# ColorOS Porting Project

</div>

## Supported Devices

- OnePlus 8, OnePlus 8 Pro, OnePlus 8T, OnePlus 9R (CN)
- OnePlus 9, OnePlus 9 Pro, OnePlus 9RT (regularly tested on the OnePlus 9 Pro)
- Oppo Find X3, Oppo Find X3 Pro

## Tested devices and port ROMs
- Test Base ROM:  OnePlus 8T (ColorOS_14.0.0.600), OnePlus 8 (ColorOS_IN2010_13.1.190), OnePlus 8 Pro (ColorOS_IN2020_13.1.0.190), OnePlus 9 Pro (OxygenOS LE2123_14.0.0.600)
- Test Port ROM: OnePlus 12 (ColorOS_14.0.0.800), OnePlus ACE3V(ColorOS_14.0.1.621), OnePlus 13T (ColorOS 16.0.2.400), OnePlus 10 Pro (OxygenOS_16.0.3.500)
- Tested mixed parts: OnePlus 15 (OxygenOS_16.0.3.501)

## Working features
- Face unlock
- Fingerprint
- Camera
- Automatic Brightness
- etc.


## Bugs
- AOD is too dim (SM8250)
- Voice trigger is not working
- Poweroff charging is not working
- Wired earphone is not working
- OnePlus 9 Pro NFC reader mode still requires a kernel/DTS fix when the kernel
  enables both the ST21/ST54 and QTI NXP stacks or lacks the `nq-nci` regulator
  entries.

## How to use
- On Debian based distros:
```shell
    sudo apt update
    sudo apt upgrade
    sudo apt install git -y
    # Clone project
    git clone https://github.com/tqmane/coloros_port.git
    cd coloros_port
    # Install dependencies
    ./setup.sh
    # Start porting
    sudo ./port.sh "<baserom>" "<portrom>"
```
- On Arch Linux based distros:
```shell
    sudo pacman -Syu git # Always keep your computer up to date!
    # yay will automatically install if it's not on your system
    # Clone project
    git clone https://github.com/tqmane/coloros_port.git
    cd coloros_port
    # Install dependencies
    ./setup.sh
    # Start porting
    sudo ./port.sh "<baserom>" "<portrom>" ["<portrom2>"]
```
- On other Linux based distros:
```shell
    # Install Distrobox. This can be done with your default package manager. If it doesn't work, install it with the following command:curl -s https://raw.githubusercontent.com/89luca89/distrobox/main/install | sudo sh
    # Start porting. All dependencies will be installed, and the script can be ran with root with this command.
    ./port_containerised.sh "<baserom>" "<portrom>" ["<portrom2>"]
``` 

- baserom, portrom and portrom2 can be a direct download link. OTAs can be acquired from sources like [Daniel Springer's OTA downloader](https://roms.danielspringer.at/index.php?view=ota). If needed, downloadCheck links can be resolved for both portrom and portrom2.
- Always quote ROM paths that contain spaces.

## Partition source safety

The port script never copies discrete firmware from the port package. Boot,
radio, bootloader, and other physical firmware partitions are preserved from
the base device.

For logical partitions, the script inspects the port ROM's `vendor` and `odm`.
It keeps the complete port logical-partition stack only when both
`ro.product.device` (when declared) and `ro.build.device_family` match the base. Otherwise it
falls back to the base device stack and applies the legacy compatibility path.
This distinction is important for hybrid packages whose `super.img` targets
the base device while bundled flasher firmware targets a different phone.
Kernel-module partitions are not taken from a newer port ROM when their kernel
ABI differs from the base kernel.

Targeted helper tests can be run with:

```shell
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

## Credits
> In this project, some or all of the content is derived from the following open-source projects. Special thanks to the developers of these projects.

- [「BypassSignCheck」by Weverses](https://github.com/Weverses/BypassSignCheck)
- [「contextpatch」 by ColdWindScholar](https://github.com/ColdWindScholar/TIK)
- [「fspatch」by affggh](https://github.com/affggh/fspatch)
- [「gettype」by affggh](https://github.com/affggh/gettype)
- [「lpunpack」by unix3dgforce](https://github.com/unix3dgforce/lpunpack)
- [「miui_port」by ljc-fight](https://github.com/ljc-fight/miui_port)
- [「Link-Resolver」by CodeSenseiX](https://github.com/CodeSenseiX/Link-Resolver/)
- [「All-day fullscreen + 1Hz LTPO AOD」by TenSei](https://t.me/TenseiMods)
