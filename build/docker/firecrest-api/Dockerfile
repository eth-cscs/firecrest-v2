# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# Base image
FROM python:3.12-slim

ARG ENVIRONMENT

EXPOSE 5000
EXPOSE 5678

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy the requirements
COPY ./requirements.txt ./requirements.txt
COPY ./requirements-testing.txt ./requirements-testing.txt



# Build the dependencies
RUN pip install --no-cache-dir --upgrade -r ./requirements.txt
RUN if [ "$ENVIRONMENT" = "development" ] ; then pip install --no-cache-dir --upgrade -r ./requirements-testing.txt ; fi


# Copy the code
COPY ./src/lib ./lib
COPY ./src/firecrest ./firecrest
COPY ./build/docker/firecrest-api/check_liveness.py ./

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Run the app with uvicorn
CMD ["uvicorn", "firecrest.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "5000"]
