#!/bin/bash
set -e

make inventory_bot_prod &
sleep 10
make reset_server
