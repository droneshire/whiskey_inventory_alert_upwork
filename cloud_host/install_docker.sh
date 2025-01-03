#!/bin/bash

set -e

# Add Docker's official GPG key:
apt update
apt install ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose docker-compose-plugin

# Droplets come with docker groups already created, AWS EC2 instances do not
groupadd docker || true
usermod -aG docker $USER || true

docker run hello-world
