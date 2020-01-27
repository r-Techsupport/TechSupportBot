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
    pip install --no-cache-dir --user -r /tmp/requirements.txt

# Production stage
FROM python:3.7-alpine
COPY --from=builder /root/.local /root/.local
COPY ./basement_bot /var/basement_bot
WORKDIR /var/basement_bot
CMD python3 -u main.py