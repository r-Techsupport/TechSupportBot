# Build stage
FROM python:3.7-alpine as builder
COPY Pipfile* /tmp/
RUN apk update && \
    apk add --no-cache \
    postgresql-dev \
    gcc \
    musl-dev
RUN pip install pipenv && \
    cd /tmp && pipenv lock --requirements > requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /var/BasementBot
COPY . .

# Production stage
FROM python:3.7-alpine
RUN apk add --no-cache \
    libpq
WORKDIR /var/basement_bot
COPY --from=builder /usr/local /usr/local
COPY --from=builder /var/BasementBot/basement_bot .
CMD python3 -u main.py