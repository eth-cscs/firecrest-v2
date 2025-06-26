# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

# commands
from datetime import datetime
from lib.exceptions import SlurmError
from lib.scheduler_clients.slurm.cli_commands.sacct_base import SacctCommandBase


def _timestr_to_seconds(timestr: str):
    try:
        time = datetime.strptime(timestr, "%H:%M:%S")
        return time.second + time.minute * 60 + time.hour * 3600
    except ValueError:
        return None


def _parse_timestamp(timestr: str):
    if timestr == "Unknown":
        return None
    try:
        return int(timestr)
    except ValueError:
        return None


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
        for job_str in stdout.split("\n"):
            job_info = job_str.split("|")
            if len(job_info) != 20:
                continue
            jobId = job_info[0]
            if "." in jobId:
                main_job_id, step_id = jobId.split(".")
                jobs[main_job_id]["steps"].append(self._parse_step(job_info))
            else:
                jobs[jobId] = self._parse_job(job_info)

        if len(jobs) == 0:
            return None
        return jobs.values()

    def _parse_job(self, job_info):
        return {
            "jobId": job_info[0],
            "allocationNodes": job_info[1],
            "cluster": job_info[2],
            "exit_code": (
                {
                    "return_code": job_info[3].split(":")[0],
                    "signal": {"id": job_info[3].split(":")[1]},
                }
                if job_info[3]
                else None
            ),
            "group": job_info[4],
            "account": job_info[5],
            "name": job_info[6],
            "nodes": job_info[7],
            "partition": job_info[8],
            "priority": job_info[9],
            "state": {"current": job_info[10], "reason": job_info[11]},
            "time": {
                "elapsed": job_info[12],
                "submission": _parse_timestamp(job_info[13]),
                "start": _parse_timestamp(job_info[14]),
                "end": _parse_timestamp(job_info[15]),
                "suspended": _timestr_to_seconds(job_info[16]),
                "limit": int(job_info[17]) if job_info[17] else None,
            },
            "user": job_info[18],
            "workingDirectory": job_info[19],
            "steps": [],
        }

    def _parse_step(self, job_info):
        return {
            "step": {"id": job_info[0], "name": job_info[6]},
            "state": job_info[10],
            "exit_code": (
                {
                    "return_code": job_info[3].split(":")[0],
                    "signal": {"id": job_info[3].split(":")[1]},
                }
                if job_info[3]
                else None
            ),
            "time": {
                "elapsed": job_info[12],
                "submission": _parse_timestamp(job_info[13]),
                "start": _parse_timestamp(job_info[14]),
                "end": _parse_timestamp(job_info[15]),
                "suspended": _timestr_to_seconds(job_info[16]),
                "limit": int(job_info[17]) if job_info[17] else None,
            },
        }
