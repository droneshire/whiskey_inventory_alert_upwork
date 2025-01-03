#!/bin/bash

set -e

REPO_DIR=$1

if [ -z "$REPO_DIR" ]; then
    echo "REPO_DIR is not set"
    exit 1
fi

echo "Setting up the droplet for repo location: $REPO_DIR"

cd $REPO_DIR

echo "Running docker-compose down"
make docker_compose_down > /dev/null 2>&1
echo "Running docker-compose up"
make docker_compose_up > /dev/null 2>&1

echo "Docker containers are up and running"

echo "You can stop the containers by running the following command:"
echo "make docker_compose_down"
