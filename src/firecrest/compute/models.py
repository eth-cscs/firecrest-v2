# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import List, Optional

# models
from lib.models import CamelModel
from lib.scheduler_clients.models import JobSubmitRequestModel
from lib.scheduler_clients.slurm.models import (
    SlurmJob,
    SlurmJobDescription,
    SlurmJobMetadata,
)


class PostJobSubmitRequest(JobSubmitRequestModel):
    job: SlurmJobDescription
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job": {
                        "name": "Count to 100",
                        "working_directory": "{{home_path}}",
                        "standard_input": "/dev/null",
                        "standard_output": "count_to_100.out",
                        "standard_error": "count_to_100.err",
                        "script": "#!/bin/bash\nfor i in {1..100}\ndo\necho $i\nsleep 1\ndone",
                    }
                }
            ]
        }
    }


class GetJobResponse(CamelModel):
    jobs: Optional[List[SlurmJob]] = None


class GetJobMetadataResponse(CamelModel):
    jobs: Optional[List[SlurmJobMetadata]] = None


class PostJobSubmissionResponse(CamelModel):
    job_id: Optional[int] = None


class PostJobAttachRequest(CamelModel):
    command: str = None
