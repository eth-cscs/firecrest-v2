FROM golang:1.24
EXPOSE 2221
EXPOSE 2280


RUN git clone --depth 1 https://github.com/wayf-dk/sshca.git

WORKDIR /go/sshca

# The sshca repo is currently under development, the state at this commit
# has been tested and vetted
RUN git fetch --depth=1 origin 6c8f316c22f510b1d4ac09c12d86ecf73049306e
RUN git checkout 6c8f316c22f510b1d4ac09c12d86ecf73049306e

COPY ./build/docker/deic-sshca/main.go ./cmd/main.go

ADD ./build/environment/keys/fireuser-key  /go/.ssh/ca-key
ADD ./build/environment/keys/fireuser.pub  /go/.ssh/ca-key.pub

COPY ./build/docker/deic-sshca/boot.sh /go/boot.sh
RUN  chmod +x /go/boot.sh

ENTRYPOINT ["/go/boot.sh"]
