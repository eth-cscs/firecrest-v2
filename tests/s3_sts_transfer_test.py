# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
from datetime import datetime, timezone
from unittest import TestCase, main
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pydantic import ValidationError

from firecrest.filesystem.transfer.models import (
    DownloadFileResponse,
    PostFileUploadRequest,
    UploadFileResponse,
)
from lib.datatransfers.datatransfer_base import (
    DataTransferLocation,
    DataTransferOperation,
    TransferJob,
    TransferJobLogs,
)
from lib.datatransfers.s3.models import S3TransferRequest, S3TransferResponse
from lib.datatransfers.s3.s3_datatransfer import S3Datatransfer


class S3STSUploadTest(TestCase):
    def test_sts_upload_returns_credentials_without_a_job(self):
        transfer = S3Datatransfer.__new__(S3Datatransfer)
        transfer.s3_client_private = AsyncMock()
        transfer.s3_client_private.exceptions.BucketAlreadyOwnedByYou = type(
            "BucketAlreadyOwnedByYou", (Exception,), {}
        )
        transfer.bucket_lifecycle_configuration = Mock()
        transfer.sts_client_private = Mock()
        transfer.sts_client_private.assume_role = AsyncMock(
            return_value={
                "Credentials": {
                    "AccessKeyId": "test-key",
                    "SecretAccessKey": "test-secret",
                    "SessionToken": "test-token",
                    "Expiration": datetime(2030, 1, 1, tzinfo=timezone.utc),
                }
            }
        )
        transfer.tenant = None
        transfer.sts_role_arn = None
        transfer.ttl = 3600
        transfer.max_part_size = 100

        app = FastAPI()

        @app.post(
            "/", response_model=UploadFileResponse, response_model_exclude_none=True
        )
        async def upload(request: PostFileUploadRequest):
            return await transfer.upload(
                source=DataTransferLocation(
                    transfer_directives=request.transfer_directives
                ),
                target=DataTransferLocation(path=request.path, system="cluster"),
                username="test-user",
                access_token="test-token",
                account=None,
            )

        response = TestClient(app).post(
            "/",
            json={
                "path": "/home/test-user/file",
                "transferDirectives": {"transferMethod": "s3", "accessMethod": "sts"},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("transferJob", body)
        self.assertEqual(body["transferDirectives"]["transferMethod"], "s3")
        self.assertEqual(
            body["transferDirectives"]["stsCredentials"]["accessKeyId"], "test-key"
        )
        self.assertEqual(
            body["transferDirectives"]["stsCredentials"]["sessionToken"], "test-token"
        )
        self.assertIsNone(UploadFileResponse.model_validate(body).transfer_job)
        transfer.sts_client_private.assume_role.assert_awaited_once()

    def test_download_still_requires_a_transfer_job(self):
        with self.assertRaises(ValidationError):
            DownloadFileResponse.model_validate(
                {"transferJob": None, "transferDirectives": {"transferMethod": "s3"}}
            )

    def test_presigned_upload_preserves_transfer_job(self):
        transfer = S3Datatransfer.__new__(S3Datatransfer)
        operation = DataTransferOperation(
            transfer_job=TransferJob(
                job_id="123",
                system="cluster",
                working_directory="/work",
                logs=TransferJobLogs(output_log="/out", error_log="/err"),
            ),
            transfer_directives=S3TransferResponse(transfer_method="s3"),
        )
        transfer.upload_presigned = AsyncMock(return_value=operation)
        source = DataTransferLocation(
            transfer_directives=S3TransferRequest(transfer_method="s3", file_size=1)
        )
        target = DataTransferLocation(path="/home/test-user/file", system="cluster")

        result = asyncio.run(transfer.upload(source, target, "test-user", "token", None))

        self.assertIs(result, operation)
        response = UploadFileResponse.model_validate(operation.model_dump())
        self.assertEqual(response.transfer_job.job_id, "123")
        transfer.upload_presigned.assert_awaited_once()


if __name__ == "__main__":
    main()
