FROM golang:1.24
EXPOSE 2221
EXPOSE 2280


RUN git clone https://github.com/wayf-dk/sshca.git

WORKDIR /go/sshca

COPY ./build/docker/deic-sshca/main.go ./cmd/main.go

ADD ./build/environment/keys/fireuser-key  /go/.ssh/ca-key
ADD ./build/environment/keys/fireuser.pub  /go/.ssh/ca-key.pub

COPY ./build/docker/deic-sshca/boot.sh /go/boot.sh
RUN  chmod +x /go/boot.sh

ENTRYPOINT ["/go/boot.sh"]
