#!/bin/bash
# port requirements


if [ "$(uname -m)" == "x86_64" ] && [  "$(uname)" == "Linux" ] && [ -f "/bin/apt" ];then
    if [ "$(id -u)" != "0" ] && [ "$(uname -m)" == "x86_64" ]  && [  "$(uname)" == "Linux" ];then
        echo "Restarting script as root"
        exec sudo /bin/bash "$0" "$@"
    fi
    echo "Device arch: Linux x86_64 (Debian based distro)"
    apt update -y
    apt upgrade -y
    apt install -y \
        aria2 bc binutils busybox curl e2fsprogs erofs-utils git jq \
        openjdk-21-jre p7zip-full python3 wget zip unzip zstd \
        android-sdk-build-tools android-sdk-libsparse-utils xmlstarlet
    if [ $? -ne 0 ];then
        echo "依赖安装失败，请检查上面的 apt 错误后重试。"
        exit 1
    fi
fi

if [ "$(uname -m)" == "x86_64" ] && [  "$(uname)" == "Linux" ] && [ -f "/bin/pacman" ];then
    echo "Device arch: Linux x86_64 (Arch based distro)"
    if [ ! -f "/bin/yay" ];then
        echo "Installing: yay. Manual intervention may be required."
        sudo pacman -Sy --needed --noconfirm base-devel && git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si
        exit
    fi
    yay -Sy --noconfirm --cleanafter --norebuild \
        aria2 android-sdk-build-tools bc binutils busybox curl e2fsprogs \
        erofs-utils git jq jdk21-openjdk python3 unzip wget xmlstarlet zip zstd 7zip
fi

if [ "$(uname -m)" == "aarch64" ];then
    echo "Device arch: aarch64"
    if [ "$(id -u)" != "0" ] && [ "$(uname)" == "Linux" ];then
        echo "Restarting script as root"
        exec sudo /bin/bash "$0" "$@"
    fi
    apt update -y
    apt upgrade -y
    apt install -y \
        aria2 bc binutils busybox curl e2fsprogs erofs-utils git jq \
        openjdk-21-jre p7zip python3 wget zip unzip zipalign zstd xmlstarlet
fi

if [ "$(uname)" == "Darwin" ] && [ "$(uname -m)" == "x86_64" ];then
    echo "Device arch: macOS x86_64"
    brew install aria2 openjdk zstd coreutils gdu gnu-sed gnu-getopt grep xmlstarlet
fi
