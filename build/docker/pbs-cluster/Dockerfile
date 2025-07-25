FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PBS_HOME="/var/spool/pbs"
ENV PBS_SERVER="localhost"

ARG PBS_VERSION=23.06.06

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
    postgresql postgresql-contrib \
    supervisor \
    sshpass \
    && rm -rf /var/lib/apt/lists/*


# Download and install PBS Pro Open Source
WORKDIR /opt
RUN wget -O pbspro.tar.gz https://github.com/openpbs/openpbs/archive/refs/tags/v${PBS_VERSION}.tar.gz \
    && tar -xzf pbspro.tar.gz \
    && cd openpbs-23.06.06 \
    && ./autogen.sh \
    && ./configure --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && rm -rf /opt/openpbs-23.06.06 /opt/pbspro.tar.gz

# Expose required ports
EXPOSE 22 5432 15001 15002 15003 15004 15005 15006 15007

# SSH setup
RUN mkdir /var/run/sshd && \
    echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config


RUN useradd -ms /bin/bash pbsuser

COPY ./build/docker/pbs-cluster/boot_pbs.sh /usr/local/bin/boot_pbs.sh
RUN chmod +x /usr/local/bin/boot_pbs.sh

COPY ./build/docker/pbs-cluster/supervisord.conf /etc/supervisor/conf.d/supervisord.conf


# Setup users
RUN useradd -m -s /bin/bash --no-user-group --gid users  fireuser  && echo 'fireuser:fireuser'       | chpasswd
RUN groupadd service-accounts
RUN useradd -m -s /bin/bash --no-user-group --gid service-accounts firesrv    && echo 'firesrv:sfiresrv'      | chpasswd

ADD --chown=fireuser:users ./build/environment/keys/fireuser.pub /home/fireuser/.ssh/authorized_keys
ADD --chown=firesrv:service-accounts ./build/environment/keys/firesrv.pub /home/firesrv/.ssh/authorized_keys

# Setup SSH keys
# use the fireuser.pub key also as a trusted ca (used for cscs keygen solution)
ADD ./build/environment/keys/fireuser.pub  /etc/ssh/ca-key.pub
RUN chmod -R 400 /etc/ssh/  && chown -R root:root /etc/ssh/
RUN /usr/bin/ssh-keygen -A


# Create the munge key
RUN dd if=/dev/urandom bs=1 count=1024 > /etc/munge/munge.key
RUN chown munge:munge /etc/munge/munge.key
RUN chmod 400 /etc/munge/munge.key
RUN mkdir -p /run/munge
RUN chown munge:munge /run/munge


CMD ["/usr/bin/supervisord"]
