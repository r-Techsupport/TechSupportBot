
FROM python:3.10-alpine as builder

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

FROM python:3.10-alpine
RUN apk add --no-cache \
    libpq
WORKDIR /var/techsupport_bot
COPY --from=builder /usr/local /usr/local
COPY --from=builder /var/TechSupportBot/techsupport_bot .
CMD python3 -u main.py
