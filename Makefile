image = rtechsupport/techsupport-bot
dev-image = $(image):dev
prod-image = $(image):prod
drun = docker run --rm -v $(shell pwd):/var/TechSupportBot -t $(dev-image) python3 -m
main_dir = techsupport_bot

make sync:
	python3 -m pipenv sync -d

check-format:
	$(drun) black --check $(main_dir)
	$(drun) isort --check-only ./$(main_dir)

format:
	$(drun) black $(main_dir)
	$(drun) isort ./$(main_dir)

lint:
	$(drun) pylint techsupport_bot/*.py techsupport_bot/base/*.py techsupport_bot/cogs/*.py
	# TODO: add techsupport_bot/plugins/*.py after plugins documented

test:
	$(drun) pytest --disable-warnings

dev:
	make establish_config
	docker build -t $(dev-image) -f Dockerfile.dev .

prod:
	make establish_config
	docker build -t $(prod-image) -f Dockerfile .

upd:
	docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

upp:
	docker-compose -f docker-compose.yml up -d

down:
	docker-compose down

reboot:
	make down && make dev && make upd && make logs

restart:
	docker-compose restart

logs:
	docker logs techsupport_bot -f

establish_config:
	@if [ ! -f "./config.yml" ]; then\
		touch ./config.yml;\
	fi
