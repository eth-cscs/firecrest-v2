# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List, Optional
from pydantic import Field

# models
from lib.models import CamelModel
from lib.scheduler_clients.models import (
    JobDescriptionModel,
    JobMetadataModel,
    JobModel,
    JobSubmitRequestModel,
)


class PostJobSubmitRequest(JobSubmitRequestModel):
    job: JobDescriptionModel
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job": {
                        "name": "Example with inline script",
                        "account": "myproject",
                        "workingDirectory": "{{home_path}}",
                        "standardInput": "/dev/null",
                        "standardOutput": "count_to_100.out",
                        "standardError": "count_to_100.err",
                        "env": {
                            "LD_LIBRARY_PATH": "/path/to/library",
                            "PATH": "/path/to/bin",
                        },
                        "script": "#!/bin/bash\n--partition=part01\nfor i in {1..100}\ndo\necho $i\nsleep 1\ndone",
                    }
                },
                {
                    "job": {
                        "name": "Example with script path",
                        "account": "myproject",
                        "workingDirectory": "{{home_path}}",
                        "standardInput": "/dev/null",
                        "standardOutput": "count_to_100.out",
                        "standardError": "count_to_100.err",
                        "env": {
                            "LD_LIBRARY_PATH": "/path/to/library",
                            "PATH": "/path/to/bin",
                        },
                        "script_path": "/path/to/batch_file.sh",
                    }
                },
            ]
        }
    }


class GetJobResponse(CamelModel):
    jobs: Optional[List[JobModel]] = None


class GetJobMetadataResponse(CamelModel):
    jobs: Optional[List[JobMetadataModel]] = None


class PostJobSubmissionResponse(CamelModel):
    job_id: Optional[int] = None


class PostJobAttachRequest(CamelModel):
    command: str = Field(default=None, description="Command to attach to the job")
    model_config = {
        "json_schema_extra": {
            "examples": [{"command": "echo 'Attached with success' > $HOME/attach.out"}]
        }
    }
