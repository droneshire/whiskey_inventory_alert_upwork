PYTHON ?= python3
PY_PATH=$(PWD)/src
RUN_PY = PYTHONPATH=$(PY_PATH) $(PYTHON) -m
BLACK_CMD = $(RUN_PY) black --line-length 100 .
# NOTE: exclude any virtual environment subdirectories here
PY_FIND_COMMAND = find -name '*.py' ! -path './venv/*'
MYPY_CONFIG=$(PY_PATH)/mypy_config.ini

init:
	$(PYTHON) -m venv venv

install:
	pip3 install -r requirements.txt

format:
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
	$(RUN_PY) executables.monitor_inventory --wait-time 60 --log-rotate

inventory_bot_dev:
	$(RUN_PY) executables.monitor_inventory --wait-time 10 --dry-run --ignore-time-window --log-level DEBUG --enable-diff-log

reset_server:
	$(RUN_PY) executables.reset_server

create_test_db:
	$(RUN_PY) database.executables.add_to_database --item 00009
	$(RUN_PY) database.executables.add_to_database --item 00005
	$(RUN_PY) database.executables.add_to_database --item 00120
	$(RUN_PY) database.executables.add_to_database --item 00137
	$(RUN_PY) database.executables.add_to_database --item 70111


.PHONY: install format check_format check_types pylint lint test creator_bot account_bot server
