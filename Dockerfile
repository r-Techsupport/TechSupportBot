FROM python:3.7-slim-buster

COPY Pipfile* /tmp/

RUN pip install pipenv && \
    cd /tmp && pipenv lock --requirements > requirements.txt && \
    pip uninstall -y pipenv && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    python -m pip uninstall -y pip && \
    rm -rf /tmp/Pipfile*

COPY ./basement_bot /basement_bot
WORKDIR /basement_bot

CMD python3 -u main.py