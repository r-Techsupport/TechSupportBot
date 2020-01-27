image = effprime/basement-bot
dev-image = $(image):dev
prod-image = $(image):latest
drun = docker run -v $(shell pwd):/app -t $(dev-image) python3 -m
main_dir = basement_bot

check-format:
	$(drun) black --check $(main_dir)
	$(drun) isort --check-only --recursive $(main_dir)

format:
	$(drun) black $(main_dir)
	$(drun) isort --recursive $(main_dir)

lint:
	$(drun) pylint basement_bot/*.py basement_bot/utils/*.py
	# TODO: add basement_bot/plugins/*.py after plugins documented

test:
	echo "No testing mechanisms exist yet. Skipping!"

dev:
	docker build -t $(dev-image) -f Dockerfile.dev .

prod:
	docker build -t $(prod-image) -f Dockerfile .

upd:
	docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

upp:
	docker-compose -f docker-compose.yml up -d

down:
	docker-compose down

logs:
	docker logs basement_bot -f