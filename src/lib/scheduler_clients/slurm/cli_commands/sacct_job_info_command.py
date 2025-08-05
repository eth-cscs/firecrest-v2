# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
import json
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.sacct_base import SacctCommandBase


class SacctCommand(SacctCommandBase):

    def get_command(self) -> str:
        cmd = [super().get_command()]
        cmd += [
            (
                "--format='JobID,AllocNodes,Cluster,ExitCode,Group,Account,JobName,NodeList,Partition,"
                "Priority,State,Reason,ElapsedRaw,Submit,Start,End,Suspended,TimelimitRaw,User,WorkDir'"
            )
        ]
        return " ".join(cmd)

    def parse_output(self, stdout: str, stderr: str, exit_status: int = 0):
        if exit_status != 0:
            raise SlurmError(
                f"Unexpected Slurm command response. exit_status:{exit_status} std_err:{stderr}"
            )

        jobs = {}
        raw_jobs = json.loads(stdout)["jobs"]
        for raw_job in raw_jobs:
            jobId = str(raw_job["job_id"])
            jobs[jobId] = self._parse_job(raw_job)

        if len(jobs) == 0:
            return None
        return jobs.values()

    def _parse_job(self, job_info):
        return {
            "jobId": str(job_info["job_id"]),
            "allocationNodes": job_info["allocation_nodes"],
            "cluster": job_info["cluster"],
            "exit_code": (
                {
                    "return_code": job_info["exit_code"]["return_code"]["number"],
                    "signal": {"id": job_info["exit_code"]["signal"]["id"]["number"]},
                }
                if "exit_code" in job_info
                else None
            ),
            "group": job_info["group"],
            "account": job_info["account"],
            "name": job_info["name"],
            "nodes": job_info["nodes"],
            "partition": job_info["partition"],
            "priority": job_info["priority"]["number"],
            "state": {
                "current": job_info["state"]["current"][0],
                "reason": job_info["state"]["reason"],
            },
            "time": {
                "elapsed": job_info["time"]["elapsed"],
                "submission": job_info["time"]["submission"],
                "start": job_info["time"]["start"],
                "end": job_info["time"]["end"],
                "suspended": job_info["time"]["suspended"],
                "limit": (
                    job_info["time"]["limit"]["number"]
                    if "limit" in job_info["time"]
                    else None
                ),
            },
            "user": job_info["user"],
            "workingDirectory": job_info["working_directory"],
            "steps": self._parse_step(job_info["steps"]),
        }

    def _parse_step(self, raw_steps):
        steps = []
        for raw_step in raw_steps:
            steps.append(
                {
                    "step": {
                        "id": raw_step["step"]["id"],
                        "name": raw_step["step"]["name"],
                    },
                    "state": raw_step["state"][0],
                    "exit_code": (
                        {
                            "return_code": raw_step["exit_code"]["return_code"][
                                "number"
                            ],
                            "signal": {
                                "id": raw_step["exit_code"]["signal"]["id"]["number"]
                            },
                        }
                        if "exit_code" in raw_step
                        else None
                    ),
                    "time": {
                        "elapsed": raw_step["time"]["elapsed"],
                        "start": raw_step["time"]["start"],
                        "end": raw_step["time"]["end"],
                        "suspended": raw_step["time"]["suspended"],
                        "limit": (
                            raw_step["time"]["limit"]["number"]
                            if "limit" in raw_step["time"]
                            else None
                        ),
                    },
                }
            )
        return steps
