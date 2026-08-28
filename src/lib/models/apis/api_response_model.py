# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import time
import fastapi
from enum import Enum
from typing import Iterator, Optional, Any, TypeVar
from pydantic import Field
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError

# exceptions
from lib.exceptions import (
    SSHServiceError,
    SchedulerAuthError,
    SchedulerError,
    SchedulerQuotaError,
)

# models
from lib.models.base_model import CamelModel
from lib.models.apis.api_auth_model import (
    ApiAuthModel,
    ApiAuthUser,
    ApiAuthServiceAccount,
)
from lib.ssh_clients.ssh_client import (
    OutputLimitExceeded,
    SSHClientError,
    SSHConnectionError,
    TimeoutLimitExceeded,
)

T = TypeVar("T", bound=Any)


# Maps exception types to an HTTP status code. Each row is `(exception types, status)`
# and is tested against the raised exception *and* every exception in its
# `__cause__` chain. Rows are evaluated top to bottom and the first match wins, so
# order them by priority (most specific / most informative first). Because every
# row is checked against the whole chain, a broad catch-all (e.g. `SchedulerError`)
# can sit at the bottom without masking the specific rows above it. Anything that
# matches no row (and is not an `HTTPException`) falls back to 500.
EXCEPTION_STATUS_CODES: tuple[tuple[tuple[type[BaseException], ...], int], ...] = (
    ((SchedulerAuthError,), fastapi.status.HTTP_401_UNAUTHORIZED),
    ((SchedulerQuotaError,), fastapi.status.HTTP_429_TOO_MANY_REQUESTS),
    ((OutputLimitExceeded,), fastapi.status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
    ((TimeoutLimitExceeded,), fastapi.status.HTTP_504_GATEWAY_TIMEOUT),
    ((SSHConnectionError,), fastapi.status.HTTP_424_FAILED_DEPENDENCY),
    ((SSHClientError, SSHServiceError), fastapi.status.HTTP_502_BAD_GATEWAY),
    ((SchedulerError,), fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR),
)

# Exception types whose message is worth surfacing in the `caused_by` chain.
REPORTABLE_CAUSE_TYPES = (SchedulerError, SSHServiceError, SSHClientError)


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
    caused_by: Optional[list[str]] = Field(default=None, nullable=True)
    data: Optional[dict] = Field(default=None, nullable=True)
    user: Optional[str] = Field(default=None, nullable=True)

    @staticmethod
    def build_http_error(
        message, error_type=ApResponseErrorType.error, caused_by=None, data=None
    ):
        model = ApiResponseError(
            error_type=error_type, message=message, caused_by=caused_by, data=data
        )
        return model

    @staticmethod
    def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
        """Yield `exc` followed by its `__cause__` chain, guarding against cycles."""
        current = exc
        visited = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            yield current
            current = current.__cause__

    @staticmethod
    def build_exception_chain(exc: Exception) -> Optional[list]:
        causes = [
            str(cause)
            for cause in ApiResponseError._exception_chain(exc)
            if cause is not exc and isinstance(cause, REPORTABLE_CAUSE_TYPES)
        ]
        return causes or None

    @staticmethod
    def _resolve_status_code(exc: Exception) -> int:
        if isinstance(exc, HTTPException):
            return exc.status_code
        chain = tuple(ApiResponseError._exception_chain(exc))
        for exc_types, status_code in EXCEPTION_STATUS_CODES:
            if any(isinstance(err, exc_types) for err in chain):
                return status_code
        return fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR

    @staticmethod
    def _resolve_message(exc: Exception) -> str:
        if isinstance(exc, HTTPException):
            return exc.detail
        if isinstance(exc, SchedulerError):
            return exc.error_msg
        if isinstance(exc, (SSHClientError, SSHServiceError)):
            return str(exc)
        if getattr(exc, "message", None):
            return exc.message
        if exc.args:
            return f"{exc.args}"
        return "An error occurred during the request process"

    @staticmethod
    def _build_validation_error(exc: RequestValidationError):
        fields = []
        for validation_error in exc.errors():
            loc = validation_error.get("loc") or ()
            fields.append(
                {
                    "location": loc[0] if len(loc) > 0 else None,
                    "name": loc[1] if len(loc) > 1 else None,
                    "message": validation_error.get("msg"),
                }
            )
        model = ApiResponseError.build_http_error(
            error_type=ApResponseErrorType.validation,
            message=str(exc).capitalize(),
            caused_by=ApiResponseError.build_exception_chain(exc=exc),
            data={"fields": fields},
        )
        return model, fastapi.status.HTTP_400_BAD_REQUEST

    @staticmethod
    def build_http_error_from_exception(exc: Exception):
        if isinstance(exc, RequestValidationError):
            return ApiResponseError._build_validation_error(exc)

        model = ApiResponseError.build_http_error(
            error_type=ApResponseErrorType.error,
            message=ApiResponseError._resolve_message(exc),
            caused_by=ApiResponseError.build_exception_chain(exc=exc),
        )
        return model, ApiResponseError._resolve_status_code(exc)
