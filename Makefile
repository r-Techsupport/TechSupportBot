image = effprime/basement-bot
full-image = $(image):prod
drun = docker run --rm -v $(shell pwd):/var/BasementBot -t $(full-image) python3 -m
main_dir = basement_bot

make sync:
	python3 -m pipenv sync -d

check-format:
	black --check ./
	isort --check-only ./

format:
	black ./
	isort ./

lint:
	$(drun) pylint basement_bot/*.py basement_bot/base/*.py basement_bot/cogs/*.py
	# TODO: add basement_bot/plugins/*.py after plugins documented

test:
	$(drun) pytest --disable-warnings

build:
	make establish_config
	docker build -t $(full-image) -f Dockerfile .

start:
	docker-compose up -d

update:
	docker-compose down
	docker-compose up -d --build

clean:
	docker system prune --volumes -a

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker logs discordBot -f

establish_config:
	@if [ ! -f "./config.yml" ]; then\
		touch ./config.yml;\
	fi
