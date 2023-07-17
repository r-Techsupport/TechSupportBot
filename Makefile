image = rtechsupport/techsupport-bot
full-image = $(image):prod
main_dir = techsupport_bot

# Dynamically set the docker command to be docker-compose or docker compose
DOCKER_COMPOSE_CMD := $(shell which docker-compose 2> /dev/null)
ifeq (,$(DOCKER_COMPOSE_CMD))
	DOCKER_COMPOSE_CMD := docker compose
endif

make sync:
	python3 -m pipenv sync -d

check-format:
	black --check ./
	isort --check-only ./ --profile black

format:
	black ./
	isort ./ --profile black

lint:
	pylint $(shell git ls-files '*.py')

test:
	PYTHONPATH=./techsupport_bot pytest techsupport_bot/tests/ -p no:warnings

build:
	make establish_config
	docker build -t $(full-image) -f Dockerfile .

rebuild:
	make build
	make start

devbuild:
	make format
	make rebuild
	make logs

start:
	$(DOCKER_COMPOSE_CMD) up -d

update:
	$(DOCKER_COMPOSE_CMD) down
	$(DOCKER_COMPOSE_CMD) up -d --build

clean:
	docker system prune --volumes -a

down:
	$(DOCKER_COMPOSE_CMD) down

reset:
	make down
	make clean
	make build
	make start

restart:
	$(DOCKER_COMPOSE_CMD) restart

logs:
	docker logs discordBot -f

establish_config:
	@if [ ! -f "./config.yml" ]; then\
		touch ./config.yml;\
	fi
