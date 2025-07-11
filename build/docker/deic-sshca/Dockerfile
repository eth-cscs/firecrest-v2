FROM golang:1.24
EXPOSE 2221
EXPOSE 2280


RUN git clone --depth 1 https://github.com/wayf-dk/sshca.git

WORKDIR /go/sshca

# The sshca repo is currently under development, the state at this commit
# has been tested and vetted
RUN git fetch --depth=1 origin 6b5bbfadb7c0d5dfd211eb91a6053f554d4dfba1
RUN git checkout 6b5bbfadb7c0d5dfd211eb91a6053f554d4dfba1

COPY ./build/docker/deic-sshca/main.go ./cmd/main.go

ADD ./build/environment/keys/fireuser-key  /go/.ssh/ca-key
ADD ./build/environment/keys/fireuser.pub  /go/.ssh/ca-key.pub

COPY ./build/docker/deic-sshca/boot.sh /go/boot.sh
RUN  chmod +x /go/boot.sh

ENTRYPOINT ["/go/boot.sh"]
