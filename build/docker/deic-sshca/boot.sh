#!/bin/bash
eval $(ssh-agent -s)
ssh-add /go/.ssh/ca-key

go run cmd/main.go