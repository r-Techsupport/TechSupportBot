image = rtechsupport/techsupport-bot
full-image = $(image):prod
drun = docker run --rm -v $(shell pwd):/var/TechSupportBot -t $(full-image) python3 -m
main_dir = techsupport_bot

make sync:
	python3 -m pipenv sync -d

check-format:
	black --check ./
	isort --check-only ./

format:
	black ./
	isort ./

lint:
	$(drun) pylint techsupport_bot/*.py techsupport_bot/base/*.py techsupport_bot/cogs/*.py
	# TODO: add techsupport_bot/plugins/*.py after plugins documented

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
