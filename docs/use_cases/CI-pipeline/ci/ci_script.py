#
#  Copyright (c) 2025, ETH Zurich. All rights reserved.
#
#  Please, refer to the LICENSE file in the root directory.
#  SPDX-License-Identifier: BSD-3-Clause
#
import firecrest as fc
import os
import time
import argparse
import utilities as util

from firecrest import FirecrestException


final_slurm_states = {
    "BOOT_FAIL",
    "CANCELLED",
    "COMPLETED",
    "DEADLINE",
    "FAILED",
    "NODE_FAIL",
    "OUT_OF_MEMORY",
    "PREEMPTED",
    "TIMEOUT",
}


def select_dict_by_name(name, list_of_dicts, select_key="name"):
    res = None
    for d in list_of_dicts:
        if d[select_key] == name:
            res = d
            break

    return res


def check_mandatory_env_var(env_var):
    r = os.environ.get(env_var)
    if not r:
        exit(1)

    return r


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--system", default=os.environ.get("FIRECREST_SYSTEM"), help="choose system to run"
    )
    parser.add_argument("--branch", default="main", help="branch to be tested")
    parser.add_argument("--account", default="csstaff", help="branch to be tested")
    parser.add_argument("--repo", help="repository to be tested")

    args = parser.parse_args()
    system_name = args.system
    ref = args.branch
    print(f"Will try to run the ci in system {system_name} on branch {ref}")

    # Setup variables of the client
    CLIENT_ID = check_mandatory_env_var("FIRECREST_CLIENT_ID")
    CLIENT_SECRET = check_mandatory_env_var("FIRECREST_CLIENT_SECRET")
    FIRECREST_URL = check_mandatory_env_var("FIRECREST_URL")
    AUTH_TOKEN_URL = check_mandatory_env_var("AUTH_TOKEN_URL")
    SYSTEM_WORKING_DIR = check_mandatory_env_var("SYSTEM_WORKING_DIR")

    keycloak = fc.ClientCredentialsAuth(CLIENT_ID, CLIENT_SECRET, AUTH_TOKEN_URL)
    client = fc.v2.Firecrest(firecrest_url=FIRECREST_URL, authorization=keycloak)

    all_systems = client.systems()
    system_names = [system["name"] for system in all_systems]
    print(f"Available systems: {', '.join(system_names)}")

    script_content = util.create_batch_script(
        repo=args.repo,
        num_nodes=2,
        account=args.account,
        custom_modules=["cray", "cray-python"],
        branch=ref,
    )

    system_state = select_dict_by_name(system_name, all_systems)
    if not system_state:
        print(f"System `{system_name}` is not available")
        exit(1)

    print(f'System info: {system_state}')

    # scheduler information
    scheduler_health_info = select_dict_by_name(
        "scheduler",
        system_state["servicesHealth"],
        "serviceType"
    )

    if scheduler_health_info["healthy"]:
        job = client.submit(
            system_name,
            working_dir=SYSTEM_WORKING_DIR,
            script_str=script_content,
        )
        print(f"Submitted job: {job['jobId']}")
        while True:
            try:
                poll_result = client.job_info(system_name, jobid=job["jobId"])
            except FirecrestException as e:
                if e.responses[-1].status_code == 404:
                    print(f"No available information yet for job {job['jobId']}")
                    time.sleep(2)
                    continue

                raise e

            print(f"Job status: {poll_result}")
            state = poll_result[0]["status"]["state"]
            if state in final_slurm_states:
                print(f"Job is in final state: {state}")
                break

            print(
                f"Status of the job is {state}, "
                f"will try again in 10 seconds"
            )
            time.sleep(10)

        stdout_file_path = os.path.join(SYSTEM_WORKING_DIR, 'job.out')
        stderr_file_path = os.path.join(SYSTEM_WORKING_DIR, 'job.err')

        print(f"\nSTDOUT in {stdout_file_path}")
        stdout_content = client.tail(system_name, path=stdout_file_path, num_lines=1000)["content"]
        print(stdout_content)

        print(f"\nSTDERR in {stderr_file_path}")
        stderr_content = client.tail(system_name, path=stderr_file_path, num_lines=1000)["content"]
        print(stderr_content)

        # Some sanity checks:
        if poll_result[0]["status"]["state"] != "COMPLETED":
            print(f"Job was not successful, status: {poll_result[0]['status']['state']}")
            exit(1)

        util.check_output(stdout_content)

    else:
        print(
            f"Scheduler of system `{system_name}` is not healthy"
        )
        exit(1)


if __name__ == "__main__":
    main()
