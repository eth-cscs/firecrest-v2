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


# Copy the UI code and install yarn to run the UI
COPY --from=ghcr.io/eth-cscs/firecrest-ui /usr/server/app /usr/server/app
RUN npm install --global yarn

ENTRYPOINT ["supervisord","-c","/etc/supervisord.conf"]