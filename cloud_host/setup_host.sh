#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

REPO_GITHUB="${REPO_GITHUB:=git@github.com:droneshire/whiskey_inventory_alert_upwork.git}"
REPO_NAME=$(basename ${REPO_GITHUB%.*})

echo -e "${GREEN}REPONAME: $REPO_NAME${NC}"
echo -e "${GREEN}REPO_GITHUB: $REPO_GITHUB${NC}"

BACKEND_ID=$1

if [ -z "$BACKEND_ID" ]; then
    echo -e "${RED}BACKEND_ID is not set${NC}"
    exit 1
fi

THIS_DIR=`pwd`
HOME_DIR=$HOME/droplet
REPO_DIR=$HOME_DIR/$REPO_NAME
ROOT_DIR=/root

CONFIG_DIR=$REPO_DIR/config
ENV_DIR=$REPO_DIR
DATABASE_DIR=$REPO_DIR/database
CONTAINERS_DIR=$REPO_DIR/containers
LOGS_DIR=$REPO_DIR/logs

FULL_INSTALL="${FULL_INSTALL:=false}"

ENV_FILE_SOURCE=$HOME_DIR/.env
ENV_FILE_DEST=$ENV_DIR/.env

FIREBASE_CREDENTIALS_FILE_SOURCE=$HOME_DIR/firebase_service_account.json
FIREBASE_CREDENTIALS_FILE_DEST=$CONFIG_DIR/firebase_service_account.json

MAKEFILE_SOURCE=$HOME_DIR/Makefile
MAKEFILE_DEST=$REPO_DIR/Makefile

COMPOSE_FILE_SOURCE=$HOME_DIR/docker-compose.yml
COMPOSE_FILE_DEST=$CONTAINERS_DIR/docker-compose.yml

INPUTRC_FILE=$HOME_DIR/inputrc

wait_for_input() {
    echo "Press any key to continue"
    set +e
    while [ true ] ; do
        read -t 3 -n 1
        if [ $? = 0 ] ; then
            break
        else
            echo "waiting for the keypress"
        fi
    done
    set -e
}

echo -e "${GREEN}Setting up the droplet${NC}"

PACKAGES="\
git \
daemon \
python3-pip \
python3-testresources \
python3-venv \
python3-gpg \
nginx \
nmap \
net-tools \
ca-certificates \
curl \
gnupg \
lsb-release \
tmux \
build-essential \
make \
protobuf-compiler \
"
echo -e "${GREEN}Installing packages${NC}"
echo -e "${BLUE}Packages: $PACKAGES${NC}"
apt -y update
apt -y install $PACKAGES

if [ "$FULL_INSTALL" = false ]; then
    echo -e "${GREEN}Minimal setup only${NC}"
else
    echo -e "${GREEN}Setting up the full droplet${NC}"
fi

if [ -d "$REPO_DIR" ]; then
    echo -e "${GREEN}Cleaning up existing repo${NC}"
    cd $REPO_DIR
    make docker_compose_down || true
fi

echo -e "${GREEN}Setting up the inputrc${NC}"
cp $INPUTRC_FILE ~/.inputrc || true
bind -f ~/.inputrc

cd $HOME_DIR
rm -rf $REPO_DIR || true

if [ "$FULL_INSTALL" = true ]; then
    echo -e "${GREEN}Setting up SSH${NC}"
    SSH_KEY=~/.ssh/id_ed25519
    KEYADD_WAIT=false
    if [ ! -f $SSH_KEY ]; then
        ssh-keygen -t ed25519 -C $REPO_NAME -f $SSH_KEY -q -N ""
        KEYADD_WAIT=true
    fi
    TMP_GITHUB_KEY=/tmp/githubKey
    ssh-keyscan github.com >> $TMP_GITHUB_KEY
    ssh-keygen -lf $TMP_GITHUB_KEY
    echo $TMP_GITHUB_KEY >> ~/.ssh/known_hosts

    # Clear all old keys
    ssh-add -D || eval "$(ssh-agent -s)" > /dev/null
    # Add the new key
    ssh-add $SSH_KEY

    ssh-add -L

    # Add the ssh key to read only Deploy Key on Github
    echo -e "${GREEN}Add the ssh key to github${NC}"

    if [ "$KEYADD_WAIT" = true ]; then
        wait_for_input
    else
        echo -e "${BLUE}Key already in github${NC}"
    fi

    echo -e "${GREEN}Cloning the repo${NC}"
    git clone $REPO_GITHUB $REPO_DIR
else
    echo -e "${GREEN}Skipping git clone${NC}"
    mkdir -p $REPO_DIR || true
fi


# Install docker
echo -e "${GREEN}Installing Docker${NC}"
./install_docker.sh

mkdir $HOME_DIR || true
cd $HOME_DIR

echo -e "${BLUE}Target directory: $REPO_DIR${NC}"

cd $REPO_DIR

mkdir -p $LOGS_DIR || true
mkdir -p $CONFIG_DIR || true
mkdir -p $DATABASE_DIR/volumes/postgres || true
mkdir -p $DATABASE_DIR/volumes/redis || true
mkdir -p $CONTAINERS_DIR || true
mkdir -p $ENV_DIR || true

cp $FIREBASE_CREDENTIALS_FILE_SOURCE $FIREBASE_CREDENTIALS_FILE_DEST || true
cp $ENV_FILE_SOURCE $ENV_FILE_DEST || true

if [ "$FULL_INSTALL" = true ]; then
    echo -e "${GREEN}Setting up the repo${NC}"
    make clean || true
    make init
    source ./venv/bin/activate
    make install
    deactivate

    # alias the repo dir to .bashrc
    echo "alias repo_root='cd $REPO_DIR'" >> ~/.bashrc
    source ~/.bashrc

    echo -e "${GREEN}Setting up tmux${NC}"

    TMUX_SESSION_NAME=$REPO_NAME-session
    tmux kill-session -t $TMUX_SESSION_NAME || true
    tmux new -d -s $TMUX_SESSION_NAME
    tmux split-window -t $TMUX_SESSION_NAME:0 -v
    tmux send-keys -t $TMUX_SESSION_NAME:0.0 "repo_root; echo 'New terminal'; source ./venv/bin/activate" C-m
    tmux send-keys -t $TMUX_SESSION_NAME:0.1 "repo_root; echo 'New terminal'; source ./venv/bin/activate" C-m

    echo -e "${GREEN}Run 'tmux attach -t $TMUX_SESSION_NAME' to reattach${NC}"
    echo -e "${BLUE}To exit a tmux session use `Ctrl+B, D`${NC}"
else
    cp $MAKEFILE_SOURCE $MAKEFILE_DEST || true
    cp $COMPOSE_FILE_SOURCE $COMPOSE_FILE_DEST || true
fi

# Replace the BACKEND_ID in the .env file
sed -i "s/^BACKEND_ID=.*/BACKEND_ID=${BACKEND_ID}/" "$ENV_FILE_DEST"

echo -e "${GREEN}Setting up containers using ${REPO_DIR}${NC}"
cd $THIS_DIR
./run_containers.sh $REPO_DIR

echo -e "${GREEN}SETUP COMPLETE! Exiting...${NC}"
