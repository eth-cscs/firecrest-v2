FROM slurm2x:latest

RUN apt update -y \
    && apt install -y \
    python3.12-full

RUN python3 -m venv /opt/jhub-env
 
RUN . /opt/jhub-env/bin/activate && \
    python3 -m pip install --no-cache \
                              jupyterlab \
                              jupyterhub==4.1.6 \
                              pyfirecrest==2.1.0 \
                              SQLAlchemy==1.4.52 \
                              oauthenticator==16.3.1 \
                              notebook==7.2.1 \
                              httpx==0.27.0
 
RUN . /opt/jhub-env/bin/activate && \
    git clone https://github.com/eth-cscs/firecrestspawner.git && \
    cd firecrestspawner && \
    pip install --no-cache . && \
    cd .. && \
    rm -r firecrestspawner
