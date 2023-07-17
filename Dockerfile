FROM python:3.11-alpine

RUN apk update
RUN apk add --no-cache postgresql-dev gcc musl-dev libpq git

WORKDIR /var/TechSupportBot

COPY Pipfile .
COPY Pipfile.lock .

RUN pip install --no-cache-dir pipenv==$(sed -nE 's/pipenv = "==(.*)"/\1/p' Pipfile)
RUN pip install --no-cache-dir "cython<3.0" pyyaml --no-build-isolation
RUN pipenv install --system

COPY . .

WORKDIR /var/TechSupportBot/techsupport_bot

CMD python3 -u main.py