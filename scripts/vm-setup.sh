# Copyright (c) 2025 Computer Networks Group @ UPB
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#!/bin/env bash

# Always run in no error conditions, otherwise it is very hard to follow in the log trace what command might have failed
set -e

# Install generic packages and toolchains
sudo apt-get update

KERNEL=$(uname -r)
# DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
sudo apt-get install -y --no-install-recommends \
  autoconf \
  automake \
  bison \
  build-essential \
  ca-certificates \
  cmake \
  cpp \
  curl \
  flex \
  git \
  libboost-dev \
  libboost-filesystem-dev \
  libboost-iostreams-dev \
  libboost-program-options-dev \
  libboost-system-dev \
  libboost-test-dev \
  libboost-thread-dev \
  libc6-dev \
  libevent-dev \
  libffi-dev \
  libfl-dev \
  libgc-dev \
  libgc1c2 \
  libgflags-dev \
  libgmp-dev \
  libgmp10 \
  libgmpxx4ldbl \
  libjudy-dev \
  libpcap-dev \
  libreadline-dev \
  libtool \
  libssl-dev \
  linux-headers-$KERNEL\
  make \
  pkg-config \
  python3-dev \
  python3-ipaddr \
  python3-pip \
  python3-psutil \
  python3-scapy \
  python3-setuptools \
  tcpdump \
  unzip \
  vim \
  wget \
  xcscope-el \
  xterm \
  git \
  mininet \
  openvswitch-switch \
  openvswitch-common \
  vlc

# Install Ryu network controller and Mininet packages
sudo pip install ryu
sudo pip install mininet

# Fix a compatability issue with eventlet
sudo pip uninstall --yes eventlet
sudo pip install eventlet==0.30.2

# Install needed Python libraries
pip install networkx
pip install matplotlib

