#!/bin/bash

# Update and install necessary packages
apt-get update
apt-get install -y \
    cmake xz-utils dh-autoreconf autoconf automake libtool m4 make gettext pkg-config \
    libdnet-dev flex g++ hwloc hwloc-dev libssl-dev libpcap-dev libpcre3 libpcre3-dev \
    luajit libluajit-5.1-dev uuid-dev libhyperscan-dev flatbuffers-dev libjemalloc-dev zlib1g zlib1g-dev \
    wget git tar build-essential check openssl libssl-dev libpcap-dev libjemalloc-dev

# Define program directory
program_dir="/root/programs"
mkdir -p "$program_dir"

# --- libdaq installation ---
cd "$program_dir"
if [ ! -d "libdaq" ]; then
    git clone https://github.com/snort3/libdaq.git
fi
cd libdaq
./bootstrap
./configure --prefix=/usr/local
make -j$(nproc)
make install
ldconfig

# --- Snort 3 installation ---
cd "$program_dir"
if [ ! -d "snort3" ]; then
    git clone https://github.com/snort3/snort3.git
fi
cd snort3
./configure_cmake.sh --enable-jemalloc --enable-shell
mkdir -p build
cd build
cmake \
  -D LUAJIT_LIBRARIES=/usr/lib/x86_64-linux-gnu/libluajit-5.1.so \
  -D LUAJIT_INCLUDE_DIR=/usr/include/luajit-2.1 \
  -D DNET_LIBRARY=/usr/local/lib/libdnet.so \
  -D DNET_INCLUDE_DIR=/usr/local/include ..
make -j$(nproc)
make install

# --- Rule-sets and IP blacklists ---
rules_dir="/usr/local/snort/etc/snort/rules"
mkdir -p "$rules_dir"

# Download and extract community rules
if [ ! -f "$rules_dir/snort3-community-rules.tar.gz" ]; then
    wget https://www.snort.org/downloads/community/snort3-community-rules.tar.gz -O /tmp/snort3-community-rules.tar.gz
    tar -xvzf /tmp/snort3-community-rules.tar.gz -C "$rules_dir"
    rm -f /tmp/snort3-community-rules.tar.gz
fi

# Download IP blacklist
wget -O "$rules_dir/ip-filter.blf" "https://snort-org-site.s3.amazonaws.com/production/document_files/files/000/035/786/original/ip-filter.blf"

# Ensure correct permissions
chmod -R 755 /usr/local/snort/etc/snort/

echo "Rules and blacklists have been placed in $rules_dir."
