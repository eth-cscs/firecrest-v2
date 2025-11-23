# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import time
import fastapi
from enum import Enum
from typing import Optional, Any, TypeVar
from pydantic import Field
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError


# exceptions
from lib.exceptions import SchedulerError, SlurmAuthTokenError

# models
from lib.models.base_model import CamelModel
from lib.models.apis.api_auth_model import (
    ApiAuthModel,
    ApiAuthUser,
    ApiAuthServiceAccount,
)
from lib.ssh_clients.ssh_client import (
    OutputLimitExceeded,
    SSHConnectionError,
    TimeoutLimitExceeded,
)


T = TypeVar("T", bound=Any)


class ApResponseErrorType(str, Enum):
    error = "error"
    validation = "validation"


class ApiResponseMeta(CamelModel):
    timestamp: float
    app_version: str
    auth: Optional[ApiAuthUser | ApiAuthServiceAccount] = Field(
        default=None, nullable=True
    )

    @staticmethod
    def build_http_meta(app_version, auth: ApiAuthModel = None):
        model = ApiResponseMeta(
            timestamp=time.time(), app_version=app_version, auth=auth
        )
        return model

    def has_auth(self) -> bool:
        return self.auth is not None

    def get_auth_username(self) -> str:
        return self.auth.username if self.auth is not None else None


class ApiResponseError(CamelModel):
    error_type: ApResponseErrorType = ApResponseErrorType.error
    message: str
    data: Optional[dict] = Field(default=None, nullable=True)
    user: Optional[str] = Field(default=None, nullable=True)

    @staticmethod
    def build_http_error(message, error_type=ApResponseErrorType.error, data=None):
        model = ApiResponseError(error_type=error_type, message=message, data=data)
        return model

    @staticmethod
    def build_http_error_from_exception(exc: Exception):
        # TODO: Customize error responses
        error_status_code = fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = ApResponseErrorType.error

        error_message = "An error occurred during the request process"
        if hasattr(exc, "message"):
            error_message = exc.message
        elif hasattr(exc, "args"):
            error_message = f"{exc.args}"

        error_data = None

        if isinstance(exc, HTTPException):
            error_status_code = exc.status_code
            error_message = exc.detail
        if isinstance(exc, SchedulerError):
            error_message = exc.error_msg
            error_status_code = fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR
            if isinstance(exc, SlurmAuthTokenError):
                error_status_code = fastapi.status.HTTP_400_BAD_REQUEST
        if isinstance(exc, OutputLimitExceeded):
            error_status_code = fastapi.status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            error_message = str(exc)
        if isinstance(exc, TimeoutLimitExceeded):
            error_status_code = fastapi.status.HTTP_408_REQUEST_TIMEOUT
            error_message = str(exc)
        if isinstance(exc, SSHConnectionError):
            error_status_code = fastapi.status.HTTP_424_FAILED_DEPENDENCY
            error_message = str(exc)
        elif isinstance(exc, RequestValidationError):
            error_status_code = fastapi.status.HTTP_400_BAD_REQUEST
            error_type = ApResponseErrorType.validation
            validation_errors = exc.errors()
            error_data_fields = []
            error_message = f"{len(validation_errors)} validation error/s occurred: "
            for validation_error in validation_errors:
                loc = validation_error.get("loc")
                location = None
                name = None
                if loc and len(loc) > 0:
                    location = loc[0]
                    if len(loc) > 1:
                        name = loc[1]
                error_data_fields.append(
                    {
                        "location": location,
                        "name": name,
                        "message": validation_error.get("msg"),
                    }
                )
                error_message += validation_error.get("msg")
            error_data = {"fields": error_data_fields}
            error_message = str(exc).capitalize()
        return (
            ApiResponseError.build_http_error(
                error_type=error_type, message=error_message, data=error_data
            ),
            error_status_code,
        )
