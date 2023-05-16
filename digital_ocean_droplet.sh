#!/bin/bash

HOME_DIR=/home/droplet
REPO_NAME=whiskey_inventory_alert_upwork
REPO_DIR=$HOME_DIR/$REPO_NAME
REPO_GITHUB=git@github.com:droneshire/whiskey_inventory_alert_upwork.git
DROPBOX_DIR=~/Dropbox/droplet_bot
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


apt -y update
apt -y install git daemon python3-pip python3-testresources python3-venv python3-gpg nginx nmap net-tools

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

mkdir -p /tmp/dropbox
mkdir -p /opt/dropbox
wget -O /tmp/dropbox/dropbox.tar.gz "https://www.dropbox.com/download?plat=lnx.x86_64"
tar xzfv /tmp/dropbox/dropbox.tar.gz --strip 1 -C /opt/dropbox
/opt/dropbox/dropboxd

# will need to link dropbox account here and
# background the dropboxd process afterwards:
# Ctrl+c

wait_for_input

curl -o /etc/init.d/dropbox https://gist.githubusercontent.com/thisismitch/6293d3f7f5fa37ca6eab/raw/2b326bf77368cbe5d01af21c623cd4dd75528c3d/dropbox
curl -o /etc/systemd/system/dropbox.service https://gist.githubusercontent.com/thisismitch/6293d3f7f5fa37ca6eab/raw/99947e2ef986492fecbe1b7bfbaa303fefc42a62/dropbox.service
sudo chmod +x /etc/systemd/system/dropbox.service /etc/init.d/dropbox

mkdir -p /etc/sysconfig
echo "DROPBOX_USERS=\"`whoami`\"" >> /etc/sysconfig/dropbox

## Create ubuntu version of /etc/systemd/system/dropbox:
cat <<EOT >> /etc/systemd/system/dropbox
#!/bin/sh

# To configure, add line with DROPBOX_USERS="user1 user2" to /etc/sysconfig/dropbox
# Probably should use a dropbox group in /etc/groups instead.

# Source function library.
. /lib/lsb/init-functions

prog=dropboxd
lockfile=${LOCKFILE-/var/lock/subsys/$prog}
RETVAL=0

start() {
    echo -n $"Starting $prog"
    echo
    if [ -z $DROPBOX_USERS ] ; then
        echo -n ": unconfigured: $config"
        echo_failure
        echo
        rm -f ${lockfile} ${pidfile}
        RETURN=6
        return $RETVAL
    fi
    for dbuser in $DROPBOX_USERS; do
        dbuser_home=`cat /etc/passwd | grep "^$dbuser:" | cut -d":" -f6`
        daemon --user $dbuser /bin/sh -c "/opt/dropbox/dropboxd"
    done
    RETVAL=$?
    echo
    [ $RETVAL = 0 ] && touch ${lockfile}
    return $RETVAL
}

status() {
    for dbuser in $DROPBOX_pUSERS; do
        dbpid=`pgrep -u $dbuser dropbox | grep -v grep`
        if [ -z $dbpid ] ; then
            echo "dropboxd for USER $dbuser: not running."
        else
            echo "dropboxd for USER $dbuser: running (pid $dbpid)"
        fi
    done
}
stop() {
    echo -n $"Stopping $prog"
    for dbuser in $DROPBOX_USERS; do
        dbuser_home=`cat /etc/passwd | grep "^$dbuser:" | cut -d":" -f6`
        dbpid=`pgrep -u $dbuser dropbox | grep -v grep`
        if [ -z $dbpid ] ; then
            echo -n ": dropboxd for USER $dbuser: already stopped."
            RETVAL=0
        else
            kill -KILL $dbpid
            RETVAL=$?
        fi
    done
    echo
    [ $RETVAL = 0 ] && rm -f ${lockfile} ${pidfile}
}

# See how we were called.
case "$1" in
    start)
        start
        ;;
    status)
        status
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        start
        ;;
    *)
        echo $"Usage: $prog {start|status|stop|restart}"
        RETVAL=3
esac
EOT

## Modify /etc/systemd/system/dropbox.service:
cat <<EOT >> /etc/systemd/system/dropbox.service
[Unit]
Description=Dropbox is a filesyncing sevice provided by dropbox.com. This service starts up the dropbox daemon.
After=network.target syslog.target

[Service]
Environment=LC_ALL=en_US.UTF-8
Environment=LANG=en_US.UTF-8
EnvironmentFile=-/etc/sysconfig/dropbox
ExecStart=/etc/systemd/system/dropbox start
ExecReload=/etc/systemd/system/dropbox restart
ExecStop=/etc/systemd/system/dropbox stop
Type=forking

[Install]
WantedBy=multi-user.target
EOT

# enable systemd service
systemctl daemon-reload
systemctl start dropbox
systemctl enable dropbox

# install dropbox cli
cd ~
wget -P ~/ -O dropbox.py https://www.dropbox.com/download?dl=packages/dropbox.py
chmod +x ~/dropbox.py
ln -s /opt/dropbox ~/.dropbox-dist

# copy logs dir if needed (should be in dropbox)
# copy config and credentials files

wait_for_input

mkdir -p $DROPBOX_DIR/logs

if [ -z "$DROPBOX_DIR/.env" ]; then
    cat <<EOT >> $DROPBOX_DIR/.env
DEFAULT_DB="inventory_manager.db"

# Configure the Twilio SMS provider.
TWILIO_FROM_SMS_NUMBER="<INSERT YOUR TWILIO SMS NUMBER HERE>"
TWILIO_AUTH_TOKEN="<INSERT YOUR TWILIO AUTH TOKEN HERE>"
TWILIO_ACCOUNT_SID="<INSERT YOUR TWILIO ACCOUNT SID HERE>"

# Website to download the inventory from
INVENTORY_DOWNLOAD_URL="https://abc.nc.gov/StoresBoards/ExportData"
INVENTORY_DOWNLOAD_KEY="------WebKitFormBoundaryf3qSjXGzLaxCryi8--\r\n"

# Admin settings
ADMIN_NAME="<INSERT YOUR ADMIN NAME HERE>"
ADMIN_PHONE="<INSERT YOUR ADMIN PHONE NUMBER HERE>"
ADMIN_EMAIL="<INSERT YOUR ADMIN EMAIL HERE>"
ADMIN_EMAIL_PASSWORD_ENCRYPTED="<INSERT YOUR ENCRYPTED ADMIN EMAIL PASSWORD HERE>"

# Firebase settings
GOOGLE_APPLICATION_CREDENTIALS="firebase_service_account.json"
EOT
fi

ln -s $DROPBOX_DIR/logs $REPO_DIR/logs
if [ ! -f "$DROPBOX_DIR/firebase_service_account.json" ]; then
    echo "Please download the firebase service account json file "
    echo "from the firebase console and place it in your dropbox folder"
    echo "as firebase_service_account.json"
    wait_for_input
fi
ln -s $DROPBOX_DIR/firebase_service_account.json $REPO_DIR/firebase_service_account.json

ln -s $DROPBOX_DIR/.env $REPO_DIR/.env

python3 -m pip install --user virtualenv
pip install wheel

# alias the repo dir to .bashrc
echo "alias inventory_bot_dir='cd $REPO_DIR'" >> ~/.bashrc
source ~/.bashrc

tmux new -s bot-session

echo "Exit this session using `Ctrl+B, D`, and then run 'tmux attach -t bot-session' to reattach"
sleep 2

tmux split-window -t bot-session:0 -v
tmux send-keys -t bot-session:0.0 "inventory_bot_dir; make init; make install; make inventory_bot_prod" C-m
tmux send-keys -t bot-session:0.1 "inventory_bot_dir; make reset_server" C-m

tmux attach-session -t bot-session
