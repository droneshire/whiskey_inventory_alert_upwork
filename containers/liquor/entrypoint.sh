#!/bin/bash
set -e

make reset_server &
make inventory_bot_prod
