check-format:
	python3 -m pipenv run python -m black --check basement_bot/*.py
	python3 -m pipenv run python -m isort --check-only basement_bot/*.py basement_bot/utils/*.py basement_bot/plugins/*.py

format:
	python3 -m pipenv run python3 -m black basement_bot/*.py
	python3 -m pipenv run python3 -m isort basement_bot/*.py basement_bot/utils/*.py basement_bot/plugins/*.py

lint:
	python3 -m pipenv run python3 -m pylint basement_bot/*.py
	python3 -m pipenv run python3 -m pylint basement_bot/utils/*.py
	# TODO: add basement_bot/plugins/*.py after plugins documented

test:
	echo "No testing mechanisms exist yet. Skipping!"

build:
	docker build -t effprime/basement-bot .

up:
	docker-compose up -d

upb:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker logs basement_bot -f