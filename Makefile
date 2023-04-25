PYTHON ?= python3
PY_PATH=$(PWD)
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
	$(RUN_PY) unittest discover -s test/ -p *_test.py -v

creator_bot:
	$(RUN_PY) bots.executables.account_creator

account_bot:
	$(RUN_PY) bots.executables.account_bot --verbose

server:
	$(RUN_PY) app --port 5000 --host localhost

.PHONY: install format check_format check_types pylint lint test creator_bot account_bot server
