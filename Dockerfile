FROM python:3.11-alpine

RUN apk update
RUN apk add --no-cache postgresql-dev gcc musl-dev libpq git

WORKDIR /var/TechSupportBot

COPY . .

RUN pip install --no-cache-dir pipenv==$(sed -nE 's/pipenv = "==(.*)"/\1/p' Pipfile)
RUN pipenv requirements > /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /var/TechSupportBot/techsupport_bot

CMD python3 -u main.py