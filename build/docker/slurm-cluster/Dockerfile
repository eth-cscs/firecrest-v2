# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

FROM ubuntu:plucky

RUN apt update -y \
    && apt install -y sudo \
    munge  \
    vim \
    build-essential \
    git \
    mariadb-server \
    openssh-server \
    wget \
    curl \
    python3 \
    python3.13-venv \
    supervisor \
    dos2unix \
    s3fs

# Install Slurm
RUN apt install -y slurmd slurmdbd slurmctld slurmrestd mpich

# Add Slurm Api user
RUN groupadd -r --gid=991 slurmapi && useradd -r -g slurmapi --uid=991 slurmapi

# Add config and helper scripts
COPY ./build/docker/slurm-cluster/slurm/*.conf /etc/slurm/
COPY ./build/docker/slurm-cluster/slurm/*.sh /
COPY ./build/docker/slurm-cluster/slurm/*.py /

RUN chmod 644 /etc/slurm/*.conf && chmod 600 /etc/slurm/slurmdbd.conf  && chown -R slurm:slurm /etc/slurm/*.conf && chmod 755 /*.sh

# Setup services
ADD ./build/docker/slurm-cluster/supervisord.conf /etc/supervisord.conf
RUN chmod 755 /*.sh
RUN dos2unix /*.sh

# Setup users
RUN useradd -m -s /bin/bash --no-user-group --gid users  fireuser && echo 'fireuser:fireuser' | chpasswd
RUN groupadd service-accounts
RUN useradd -m -s /bin/bash --no-user-group --gid service-accounts firesrv  && echo 'firesrv:sfiresrv' | chpasswd

ADD --chown=fireuser:users ./build/environment/keys/fireuser.pub /home/fireuser/.ssh/authorized_keys
ADD --chown=firesrv:service-accounts ./build/environment/keys/firesrv.pub /home/firesrv/.ssh/authorized_keys

# Setup SSH keys
# use the fireuser.pub key also as a trusted ca (used for cscs keygen solution)
ADD ./build/environment/keys/fireuser.pub  /etc/ssh/ca-key.pub
RUN chmod -R 400 /etc/ssh/  && chown -R root:root /etc/ssh/
RUN /usr/bin/ssh-keygen -A

# Setup MariaDB
RUN mkdir -p /run/mariadb && chown mysql:mysql /run/mariadb

# Setup Munge
RUN mkdir -p /run/munge && chown -R munge:munge /var/log/munge  && chown -R munge:munge /var/lib/munge  && chown -R munge:munge /run/munge && chown 755 /var/log/munge && chmod 755 /run/munge && chmod 755 /var/lib/munge

# Scratch S3 filesystem
RUN mkdir -p /s3/fireuser && mkdir -p /s3/firesrv
RUN chmod 711 /s3 && chmod -R 700 /s3/* && chown fireuser /s3/fireuser && chown firesrv /s3/firesrv
# S3fS credentials
RUN mkdir -p /etc/s3fs && \
    echo "fireuser_access_key:fireuser_secret_key" > /etc/s3fs/s3fs_creds_fireuser && \
    echo "firesrv_access_key:firesrv_secret_key" > /etc/s3fs/s3fs_creds_firesrv && \
    chmod 700 /etc/s3fs && chmod 600 /etc/s3fs/*

ENTRYPOINT ["supervisord"]
