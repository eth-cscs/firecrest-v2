#
#  Copyright (c) 2025, ETH Zurich. All rights reserved.
#
#  Please, refer to the LICENSE file in the root directory.
#  SPDX-License-Identifier: BSD-3-Clause
#
current_dir := $(shell pwd)

build:
	docker image rm -f f7t-demo-ui
	docker build -f ./docker/Dockerfile -t f7t-demo-ui .
run:
	docker run --rm -p 9091:9091 -v ${current_dir}/log:/var/log  --name f7t-demo-ui f7t-demo-ui
stop:
	docker stop f7t-demo-ui