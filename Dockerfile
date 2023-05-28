
FROM python:3.11-alpine as builder

RUN apk update && \
    apk add --no-cache \
    postgresql-dev \
    gcc \
    musl-dev

WORKDIR /var/TechSupportBot
COPY Pipfile.lock .

RUN pip install pipenv && \
    pipenv requirements > /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt

COPY . .

FROM python:3.11-alpine
RUN apk add --no-cache \
    libpq \
    git
WORKDIR /var/TechSupportBot
COPY --from=builder /usr/local /usr/local
COPY --from=builder /var/TechSupportBot/. .
WORKDIR /var/TechSupportBot/techsupport_bot
CMD python3 -u main.py
