DOCKER_COMPOSE_CMD := $(shell command -v docker-compose 2> /dev/null || echo "docker compose")


GREEN=\033[0;32m
NORMAL=\033[0m

DOCKER_REGISTRY_REPO_NAME?=liquor-tracker
DOCKER_USERNAME?=ryeager12

PYTHON_IMAGE=liquor
PYTHON_CONTAINER_NAME=$(PYTHON_IMAGE)_container


###########
### Docker Compose
### The _compose_ versions of the docker commands pull images from a registry
###########
docker_compose_clean:
	docker image prune -a
	docker system prune -a --volumes

docker_compose_up:
	$(DOCKER_COMPOSE_CMD) -f containers/docker-compose.yml up -d

docker_compose_down:
	$(DOCKER_COMPOSE_CMD) -f containers/docker-compose.yml down -v

.PHONY: docker_compose_clean docker_compose_up docker_compose_down