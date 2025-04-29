FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install required dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gcc \
    make \
    libssl-dev \
    libtool \
    libhwloc-dev \
    libx11-dev \
    libxt-dev \
    libedit-dev \
    libmunge-dev \
    libpq-dev \
    libical-dev \
    swig \
    tcl-dev \
    munge \
    vim \
    curl \
    tk-dev \
    tk8.6-dev \
    python3-dev \
    python3 \
    python3-pip \
    wget curl vim git \
    build-essential libtool autoconf automake \
    libtool-bin g++ gcc \
    libhwloc-dev libx11-dev libxt-dev \
    libedit-dev libical-dev ncurses-dev \
    perl python3-dev tcl-dev tk-dev swig \
    libexpat-dev libssl-dev \
    openssh-server \
    # postgresql postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*


# Download and install PBS Pro Open Source
WORKDIR /opt
RUN wget -O pbspro.tar.gz https://github.com/openpbs/openpbs/archive/refs/tags/v23.06.06.tar.gz \
    && tar -xzf pbspro.tar.gz \
    && cd openpbs-23.06.06 \
    && ./autogen.sh \
    && ./configure --prefix=/opt/pbs \
    && make -j$(nproc) \
    && make install \
    && rm -rf /opt/openpbs-23.06.06 /opt/pbspro.tar.gz


# Set up PBS environment
ENV PATH="/opt/pbs/bin:/opt/pbs/sbin:$PATH"
ENV PBS_HOME="/var/spool/pbs"
ENV LD_LIBRARY_PATH="/opt/pbs/lib:$LD_LIBRARY_PATH"
ENV PBS_SERVER="localhost"

# Expose required ports
EXPOSE 22 15001 15002 15003 15004 15005 15006 15007

# SSH setup
RUN mkdir /var/run/sshd && \
    echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config

# Post-install setup and entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -ms /bin/bash pbsuser

RUN apt-get update && apt-get install -y postgresql postgresql-contrib && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*


RUN apt-get update && apt-get install -y sshpass && rm -rf /var/lib/apt/lists/*

# USER pbsuser

# WORKDIR /home/pbsuser

# CMD ["/entrypoint.sh"]

COPY init_sequence.sh /usr/local/bin/init_sequence.sh
RUN chmod +x /usr/local/bin/init_sequence.sh

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 22 5432

CMD ["/usr/bin/supervisord"]
