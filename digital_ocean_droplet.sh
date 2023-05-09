#!/bin/bash

HOME_DIR=/home/droplet
REPO_NAME=whiskey_inventory_alert_upwork
REPO_DIR=$HOME_DIR/$REPO_NAME
REPO_GITHUB=git@github.com:droneshire/whiskey_inventory_alert_upwork.git

DROPBOX_DIR=/root/Dropbox/droplet_bot
EMAIL="test@gmail.com"

wait_for_input() {
    echo "Press any key to continue"
    while [ true ] ; do
        read -t 3 -n 1
        if [ $? = 0 ] ; then
            break
        else
            echo "waiting for the keypress"
        fi
    done
}


echo "deb [arch=i386,amd64] http://linux.dropbox.com/ubuntu disco main" >> /etc/apt/sources.list.d/dropbox.list
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 1C61A2656FB57B7E4DE0F4C1FC918B335044912E
apt -y update
apt -y install dropbox

apt -y update
apt -y install git python3-pip python3-testresources python3-venv python3-gpg nginx nmap net-tools

ssh-keygen -t ed25519 -C $EMAIL -f /root/.ssh/id_ed25519 -q -N ""

TMP_GITHUB_KEY=/tmp/githubKey
ssh-keyscan github.com >> $TMP_GITHUB_KEY
ssh-keygen -lf $TMP_GITHUB_KEY
echo $TMP_GITHUB_KEY >> ~/.ssh/known_hosts
ssh-add ~/.ssh/id_ed25519

mkdir -p $HOME_DIR
mkdir -p $HOME_DIR/logs
mkdir -p $HOME_DIR/logs/bot
mkdir -p $HOME_DIR/logs/server

cd $HOME_DIR

cat ~/.ssh/id_ed25519.pub

# add deploy keys to github
wait_for_input

git clone $REPO_GITHUB $REPO_DIR

python3 -m pip install --user virtualenv

cd $REPO_DIR
python3 -m venv env
source env/bin/activate

pip install wheel
pip install -r requirements.txt

dropbox start -i

# will need to approve the device here

mkdir -p $DROPBOX_DIR/logs
ln -s $DROPBOX_DIR/logs $REPO_DIR/logs

# copy logs dir if needed (should be in dropbox)
# copy config and credentials files

sudo ufw allow OpenSSH
sudo ufw allow 'Nginx HTTP'
sudo ufw enable

wait_for_input

tmux new -s bot-session
cd $REPO_DIR

echo "Exit this session using `Ctrl+B, D`, and then run 'tmux attach -t bot-session' to reattach"
