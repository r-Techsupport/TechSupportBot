check-format:
	python3 -m pipenv run python -m black --check basement_bot/*.py
	python3 -m pipenv run python -m isort --check-only basement_bot/*.py basement_bot/plugins/*.py

format:
	python3 -m pipenv run python -m black basement_bot/*.py
	python3 -m pipenv run python -m isort basement_bot/*.py basement_bot/plugins/*.py

test:
	echo "No testing mechanisms exist yet. Skipping!"

build:
	docker build -t effprime/basement-bot .

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker logs basement_bot -f