# syntax=docker/dockerfile:1
FROM python:3

WORKDIR ./app
COPY . .
RUN chmod 775 script.sh

#ENV PYTHONDONTWRITEBYTECODE 1
#ENV PYTHONUNBUFFERED 1


RUN pip install --upgrade pip && pip install --no-cache-dir --upgrade -r requirements.txt

RUN apt update
RUN apt install -y wget
RUN mkdir -p ~/.postgresql && \
    wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" -O ~/.postgresql/root.crt && \
    chmod 0600 ~/.postgresql/root.crt


RUN apt-get update && apt-get install cron -y
RUN touch /etc/cron.d/ecomactionslist
RUN chmod 0644 /etc/cron.d/ecomactionslist
ADD crontab /etc/cron.d/ecomactionslist
RUN crontab /etc/cron.d/ecomactionslist


