# from __future__ import annotations

import datetime
import os
import pendulum

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.filesystem import FileSensor

from firecrest_airflow_operators import (FirecRESTSubmitOperator,
                                         FirecRESTUploadOperator,
                                         FirecRESTDownloadFromJobOperator)


workdir = '/path/to/local/dir'  # directory on local workstation
remotedir = '/path/to/remote/dir'  # directory on remote HPC system
username = '<username>'  # username on the HPC system
system = '<system>'  # HPC system name

job_script = """#!/bin/bash -l

#SBATCH --job-name=airflow-example
#SBATCH --output=slurm-%j.out
#SBATCH --time=00:05:00
#SBATCH --nodes=1

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

uenv repo create
uenv image pull quantumespresso/v7.3.1:v2

srun --uenv quantumespresso/v7.3.1:v2 --view default pw.x -in si.scf.in
"""

with DAG(
    dag_id="firecrest_example",
    schedule="@daily",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=["firecrest-v2-demo"],
) as dag:

    wait_for_file = FileSensor(
        task_id="wait-for-file",
        filepath=os.path.join(workdir, "structs", "si.scf.in"),
        poke_interval=10
    )

    upload_in = FirecRESTUploadOperator(
        task_id="upload-in",
        system=system,
        source_path=os.path.join(workdir, "structs", "si.scf.in"),
        target_path=remotedir
    )

    upload_pp = FirecRESTUploadOperator(
        task_id="upload-pp",
        system=system,
        source_path=os.path.join(workdir, "Si.pz-vbc.UPF"),
        target_path=remotedir
    )

    submit_task = FirecRESTSubmitOperator(
        task_id="job-submit",
        system=system, 
        script=job_script,
        working_dir=remotedir
    )

    download_out_task = FirecRESTDownloadFromJobOperator(
        task_id="download-out",
        system=system,
        remote_files = ["slurm-{_jobid_}.out"],
        local_path=os.path.join(workdir, "output.out"),
        target_task_id="job-submit"
    )

    download_xml_task = FirecRESTDownloadFromJobOperator(
        task_id="download-xml",
        system=system,
        remote_files = ['output/silicon.xml'],
        local_path=os.path.join(workdir, "silicon.xml"),
        target_task_id="job-submit"
    )

    log_results = BashOperator(
        task_id="log-results",
        bash_command=(f"echo $(date) '  |  ' "
                      f"$(grep '!    total energy' {workdir}/output.out) >> {workdir}/list.txt"),
    )

    remove_struct = BashOperator(
        task_id="remove-struct",
        bash_command=(f"rm {workdir}/structs/si.scf.in"),
    )

    wait_for_file >> upload_in
    wait_for_file >> upload_pp
    upload_in >> submit_task >> download_out_task >> log_results
    submit_task >> download_xml_task
    upload_pp >> submit_task
    upload_in >> remove_struct


if __name__ == "__main__":
    dag.test()