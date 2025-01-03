PYTHON ?= python3
PIP ?= pip3
PIP_COMPILE = pip-compile

# Core paths
LOG_PATH=$(PWD)/logs
CONFIG_PATH=$(PWD)/config
SOURCE_PATH=$(PWD)/src
PACKAGES_PATH=$(PWD)/packages
DROPLET_DEST_DIR ?= /root/droplet
DROPLET_BACKEND_ID=whiskey_inventory_alert_upwork
PY_VENV=$(PWD)/venv
PY_SITE_PACKAGES=$(PY_VENV)/lib/python3.12/site-packages

PY_PATH=$(SOURCE_PATH)

RUN_PY_DIRECT = PYTHONPATH=$(PY_PATH) $(PYTHON) -m
RUN_PY= $(RUN_PY_DIRECT)

# NOTE: exclude any virtual environment subdirectories here
PY_VENV_REL_PATH=$(subst $(PWD)/,,$(PY_VENV))
PY_FIND_COMMAND = find . -name '*.py' | grep -vE "($(PY_VENV_REL_PATH))"
BLACK_CMD = $(RUN_PY_DIRECT) black --line-length 100 $(shell $(PY_FIND_COMMAND))
# Consolidated mypy config to pyproject.toml
MYPY_CONFIG=$(SOURCE_PATH)/mypy_config.ini


sync_files:
	./cloud_host/flatten_makefile.sh ./Makefile
	scp -r ./config/* $(SSH_CONFIG_ALIAS):$(DROPLET_DEST_DIR)/$(DROPLET_BACKEND_ID)/config
	scp .env $(SSH_CONFIG_ALIAS):$(DROPLET_DEST_DIR)/$(DROPLET_BACKEND_ID)
	scp ./Makefile.flattened $(SSH_CONFIG_ALIAS):$(DROPLET_DEST_DIR)/$(DROPLET_BACKEND_ID)/Makefile
	scp ./containers/docker-compose.yml $(SSH_CONFIG_ALIAS):$(DROPLET_DEST_DIR)/$(DROPLET_BACKEND_ID)/containers


sync_droplet_bootstrap:
	./cloud_host/flatten_makefile.sh ./Makefile
	ssh $(SSH_CONFIG_ALIAS) "mkdir -p $(DROPLET_DEST_DIR)"
	scp ./containers/docker-compose.yml $(SSH_CONFIG_ALIAS):$(DROPLET_DEST_DIR)
	scp ./Makefile.flattened $(SSH_CONFIG_ALIAS):$(DROPLET_DEST_DIR)/Makefile
	scp -r ./config/* \
		.env \
		./cloud_host/setup_host.sh \
		./cloud_host/install_docker.sh \
		./cloud_host/run_containers.sh \
		./cloud_host/inputrc \
		$(SSH_CONFIG_ALIAS):$(DROPLET_DEST_DIR)
	ssh $(SSH_CONFIG_ALIAS) "chmod +x $(DROPLET_DEST_DIR)/setup_host.sh \
		$(DROPLET_DEST_DIR)/install_docker.sh \
		$(DROPLET_DEST_DIR)/run_containers.sh"

config_droplet: sync_droplet_bootstrap
	echo "Configuring droplet with backend id: $(DROPLET_BACKEND_ID)"
	ssh $(SSH_CONFIG_ALIAS) "cd $(DROPLET_DEST_DIR) && ./setup_host.sh $(DROPLET_BACKEND_ID)"

create_dirs:
	mkdir -p $(LOG_PATH)
	mkdir -p $(CONFIG_PATH)

init: create_dirs
	$(PYTHON) -m venv $(PY_VENV_REL_PATH)

install:
	$(PIP) install --upgrade pip
	$(PIP) install pip-tools
	$(PIP_COMPILE) --strip-extras --output-file=$(PACKAGES_PATH)/requirements.txt $(PACKAGES_PATH)/base_requirements.in
	$(PIP) install -r $(PACKAGES_PATH)/requirements.txt

format: isort
	$(BLACK_CMD)

check_format:
	$(BLACK_CMD) --check --diff

mypy:
	$(RUN_PY) mypy $(shell $(PY_FIND_COMMAND)) --config-file $(MYPY_CONFIG) --no-namespace-packages

pylint:
	$(RUN_PY) pylint $(shell $(PY_FIND_COMMAND))

autopep8:
	autopep8 --in-place --aggressive --aggressive $(shell $(PY_FIND_COMMAND))

isort:
	isort $(shell $(PY_FIND_COMMAND))

lint: check_format mypy pylint

test:
	$(RUN_PY) unittest discover -s test -p *_test.py -v

inventory_bot_prod:
	$(RUN_PY) executables.monitor_inventory --wait-time 60 --log-rotate --enable-alarm

inventory_bot_dev:
	$(RUN_PY) executables.monitor_inventory --wait-time 10 --dry-run --ignore-time-window --log-level DEBUG --enable-diff-log --allowlist-clients ryeager12@gmail.com

reset_server:
	$(RUN_PY) executables.reset_server

create_test_db:
	$(RUN_PY) database.executables.add_to_database --item 00009
	$(RUN_PY) database.executables.add_to_database --item 00005
	$(RUN_PY) database.executables.add_to_database --item 00120
	$(RUN_PY) database.executables.add_to_database --item 00137
	$(RUN_PY) database.executables.add_to_database --item 70111

clean:
	rm -rf ./logs/*
	rm -rf $(PY_VENV)

###########
### Docker Compose
### The _compose_ versions of the docker commands pull images from a registry
###########
DOCKER_REGISTRY_REPO_NAME?=liquor-tracker
DOCKER_USERNAME?=ryeager12
DOCKER_COMPOSE_CMD := $(shell command -v docker-compose 2> /dev/null || echo "docker compose")

docker_compose_clean:
	docker image prune -a
	docker system prune -a --volumes

docker_compose_up:
	$(DOCKER_COMPOSE_CMD) -f containers/docker-compose.yml up -d

docker_compose_down:
	$(DOCKER_COMPOSE_CMD) -f containers/docker-compose.yml down -v

.PHONY: docker_compose_clean docker_compose_up docker_compose_down
.PHONY: sync_files sync_droplet_bootstrap config_droplet
.PHONY: init install format check_format check_types pylint
.PHONY: lint test creator_bot account_bot server reset_server
.PHONY: create_test_db clean inventory_bot_prod inventory_bot_dev create_dirs