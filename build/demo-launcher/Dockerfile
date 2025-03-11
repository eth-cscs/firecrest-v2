# Base image
FROM python:3.12-slim

ARG ENVIRONMENT

EXPOSE 8080


# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV YAML_CONFIG_FILE="/app/config/app-config.yaml"


RUN apt update -y \
    && apt install -y sudo \
    supervisor \
    iputils-ping \
    && curl -fsSL https://deb.nodesource.com/setup_21.x | bash - \
    && apt install -y nodejs npm

RUN mkdir /run/secrets


# Set the working directory
WORKDIR /app

# Copy the requirements
COPY ./requirements.txt ./requirements.txt
COPY ./requirements-testing.txt ./requirements-testing.txt


# Build the dependencies
RUN pip install --no-cache-dir --upgrade -r ./requirements.txt
RUN pip install --no-cache-dir --upgrade -r ./requirements-testing.txt

# Copy the code
COPY ./build/demo-launcher/src/launcher/ ./launcher
COPY ./src/firecrest/ ./firecrest/
COPY ./src/lib/ ./lib/
COPY ./build/demo-launcher/src/launcher/f7t-api-config.demo-env.yaml  ./config/app-config.yaml

ADD ./build/demo-launcher/supervisord.conf /etc/supervisord.conf


# Copy the UI code
COPY --from=ghcr.io/eth-cscs/firecrest-ui /usr/server/app ./web-ui
RUN npm install --global yarn


ENV APP_VERSION='local'
ENV ENVIRONMENT='development'
ENV SERVICE_NAME='firecrest-web-ui'
ENV COMPANY_NAME='CSCS'

ENV LOGGING_LEVEL='debug'
ENV SESSION_SECRET='s3cr3t'
ENV SESSION_FILE_SECRET='s3cr3tfile'
ENV SESSION_FILE_DIR_PATH='./sessions'
ENV REDIS_ACTIVE=false
ENV SENTRY_ACTIVE=false

ENV KEYCLOAK_DOMAIN='localhost:8080/auth'
ENV KEYCLOAK_REALM='kcrealm'
ENV KEYCLOAK_CLIENT_ID='firecrest-web-ui'
ENV KEYCLOAK_CLIENT_SECRET='secret'
ENV KEYCLOAK_CALLBACK_URL='http://localhost:3000/auth/callback'
ENV KEYCLOAK_LOGOUT_REDIRECT_URL='http://localhost:3000/'
ENV KEYCLOAK_USE_SSL=false

ENV FIRECREST_API_BASE_URL='http://localhost:5000'
ENV UI_HOSTNAME='localhost:3000'
ENV SUPPORT_URL='<support-url>'


ENTRYPOINT ["supervisord","-c","/etc/supervisord.conf"]