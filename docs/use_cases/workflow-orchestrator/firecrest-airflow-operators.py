import os
import tempfile
import time

from firecrest import ClientCredentialsAuth
from firecrest.v2 import Firecrest as Firecrest
from airflow.models.baseoperator import BaseOperator
from airflow import AirflowException

# Workaround to run tasks that do http requests from the Airflow UI
# on arm64 macs
# https://github.com/apache/airflow/discussions/24463#discussioncomment-4404542
# Other discussions on the topic:
# https://stackoverflow.com/questions/75980623/why-is-my-airflow-hanging-up-if-i-send-a-http-request-inside-a-task  # noqa E501
import platform


if platform.processor() == 'arm' and platform.system() == 'Darwin':
    from _scproxy import _get_proxy_settings
    _get_proxy_settings()


class FirecRESTBaseOperator(BaseOperator):
    firecrest_url = os.environ['FIRECREST_URL']
    client_id = os.environ['FIRECREST_CLIENT_ID']
    client_secret = os.environ['FIRECREST_CLIENT_SECRET']
    token_uri = os.environ['AUTH_TOKEN_URL']

    keycloak = ClientCredentialsAuth(
        client_id, client_secret, token_uri
    )

    client = Firecrest(firecrest_url=firecrest_url, authorization=keycloak)


class FirecRESTSubmitOperator(FirecRESTBaseOperator):
    """Airflow Operator to submit a job via FirecREST"""

    def __init__(
            self,
            system: str,
            script: str,
            working_dir: str,
            **kwargs
        ) -> None:
        super().__init__(**kwargs)
        self.system = system
        self.script = script
        self.working_dir = working_dir

    def execute(self, context):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(bytes(self.script, 'utf-8'))
            tmp.seek(0)
            job = self.client.submit(
                self.system,
                script_str=self.script,
                working_dir=self.working_dir
            )
            time.sleep(10)

        while True:
            job_info = self.client.job_info(
                self.system,
                job['jobId']
            )

            job_status = job_info[0]["status"]["state"]
            if job_status not in ("PENDING", "RUNNING"):
                self.log.info(f"Job status: {job_status}")
                break

            time.sleep(10)

        job_info = self.client.job_info(
            self.system,
            job['jobId']
        )
        if job_info[0]['status']['state'] != 'COMPLETED':
            raise AirflowException(f"Job state: {job_info[0]['status']['state']}")

        return job


class FirecRESTDownloadOperator(FirecRESTBaseOperator):
    """Airflow Operator to fetch files within the workdir of a job
    submitted via FirecREST"""

    def __init__(self,
                 system: str,
                 remote_files: list,
                 local_path: str,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.system = system
        self.remote_files = remote_files
        self.local_path = local_path

    def execute(self, context):
        for remote_file in self.remote_files:
            try:
                self.client.download(
                    self.system,
                    remote_file,
                    self.local_path,
                    blocking=True
                )
            except Exception as e:
                raise AirflowException(f"File`{remote_file}` failed to "
                                       f"download: {e}")


class FirecRESTDownloadFromJobOperator(FirecRESTBaseOperator):
    """Airflow Operator to fetch files within the workdir of a job
    submitted via FirecREST"""

    def __init__(self,
                 system: str,
                 remote_files: list,
                 local_path: str,
                 target_task_id: str,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.system = system
        self.remote_files = remote_files
        self.local_path = local_path
        self.target_task_id = target_task_id

    def execute(self, context):
        job = context["ti"].xcom_pull(key="return_value",
                                      task_ids=self.target_task_id)
        # currently the workdir is the directory where the job script is
        job_info = self.client.job_info(
                self.system,
                job['jobId']
            )
        workdir = job_info[0]["workingDirectory"]
        # download job's output
        for remote_file in self.remote_files:
            try:
                self.client.download(
                    self.system,
                    os.path.join(workdir, remote_file.format(_jobid_=job['jobId'])),
                    self.local_path.format(_jobid_=job['jobId']),
                )
            except Exception as e:
                raise AirflowException(f"File`{remote_file}` failed to "
                                       f"download: {e}")


class FirecRESTUploadOperator(FirecRESTBaseOperator):
    """Airflow Operator to updload the input file for a job
    to be submitted via FirecREST later in the DAG"""

    def __init__(self,
                 system: str,
                 source_path: str,
                 target_path: str,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.system = system
        self.source_path = source_path
        self.target_path = target_path

    def execute(self, context):
        self.client.upload(
            self.system,
            self.source_path,
            self.target_path,
        )
