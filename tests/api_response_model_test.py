# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import fastapi
import pytest
from starlette.exceptions import HTTPException

# exceptions
from lib.exceptions import (
    SchedulerAuthError,
    SchedulerError,
    SchedulerQuotaError,
    SSHServiceError,
)
from lib.ssh_clients.ssh_client import (
    OutputLimitExceeded,
    SSHClientError,
    SSHConnectionError,
    TimeoutLimitExceeded,
)

# models
from lib.models.apis.api_response_model import (
    ApiResponseError,
    ApResponseErrorType,
    EXCEPTION_STATUS_CODES,
)


# One case per exception referenced in `EXCEPTION_STATUS_CODES`. The
# `test_all_mapped_exceptions_have_a_case` test below fails if the map grows a
# row that is not represented here.
EXCEPTION_CASES = [
    pytest.param(
        SchedulerAuthError("auth rejected"),
        fastapi.status.HTTP_401_UNAUTHORIZED,
        id="SchedulerAuthError",
    ),
    pytest.param(
        SchedulerQuotaError("quota exceeded"),
        fastapi.status.HTTP_403_FORBIDDEN,
        id="SchedulerQuotaError",
    ),
    pytest.param(
        OutputLimitExceeded("output too large"),
        fastapi.status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        id="OutputLimitExceeded",
    ),
    pytest.param(
        TimeoutLimitExceeded("command timed out"),
        fastapi.status.HTTP_504_GATEWAY_TIMEOUT,
        id="TimeoutLimitExceeded",
    ),
    pytest.param(
        SSHConnectionError("connection refused"),
        fastapi.status.HTTP_424_FAILED_DEPENDENCY,
        id="SSHConnectionError",
    ),
    pytest.param(
        SSHClientError("ssh client failure"),
        fastapi.status.HTTP_502_BAD_GATEWAY,
        id="SSHClientError",
    ),
    pytest.param(
        SSHServiceError("ssh service failure"),
        fastapi.status.HTTP_502_BAD_GATEWAY,
        id="SSHServiceError",
    ),
    pytest.param(
        SchedulerError("generic scheduler failure"),
        fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
        id="SchedulerError",
    ),
]


def _all_mapped_exception_types() -> set[type[BaseException]]:
    types: set[type[BaseException]] = set()
    for exc_types, _ in EXCEPTION_STATUS_CODES:
        types.update(exc_types)
    return types


@pytest.mark.parametrize("exc, expected_status", EXCEPTION_CASES)
def test_resolve_status_code_for_raised_exception(exc, expected_status):
    assert ApiResponseError._resolve_status_code(exc) == expected_status


@pytest.mark.parametrize("exc, expected_status", EXCEPTION_CASES)
def test_resolve_status_code_walks_the_cause_chain(exc, expected_status):
    # The mapped exception is buried two levels deep in the `__cause__` chain of
    # an otherwise unmapped exception.
    middle = RuntimeError("middle wrapper")
    middle.__cause__ = exc
    outer = RuntimeError("outer wrapper")
    outer.__cause__ = middle

    assert ApiResponseError._resolve_status_code(outer) == expected_status


@pytest.mark.parametrize("exc, expected_status", EXCEPTION_CASES)
def test_build_http_error_from_exception(exc, expected_status):
    model, status_code = ApiResponseError.build_http_error_from_exception(exc)

    assert status_code == expected_status
    assert model.error_type == ApResponseErrorType.error
    assert model.message


def test_all_mapped_exceptions_have_a_case():
    tested_types = {type(case.values[0]) for case in EXCEPTION_CASES}
    assert tested_types == _all_mapped_exception_types()


def test_more_specific_row_wins_over_broader_row():
    # `SSHConnectionError` is a subclass of `SSHClientError`; its dedicated row
    # sits above the `SSHClientError` row, so the specific status must win.
    exc = SSHConnectionError("connection refused")
    assert (
        ApiResponseError._resolve_status_code(exc)
        == fastapi.status.HTTP_424_FAILED_DEPENDENCY
    )

    # `SchedulerAuthError` is a subclass of `SchedulerError`; the catch-all
    # `SchedulerError` row at the bottom must not mask the 401 row.
    exc = SchedulerAuthError("auth rejected")
    assert (
        ApiResponseError._resolve_status_code(exc)
        == fastapi.status.HTTP_401_UNAUTHORIZED
    )


def test_unmapped_exception_falls_back_to_500():
    assert (
        ApiResponseError._resolve_status_code(ValueError("nope"))
        == fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def test_http_exception_status_is_passed_through():
    exc = HTTPException(status_code=fastapi.status.HTTP_418_IM_A_TEAPOT, detail="teapot")
    assert (
        ApiResponseError._resolve_status_code(exc)
        == fastapi.status.HTTP_418_IM_A_TEAPOT
    )

    model, status_code = ApiResponseError.build_http_error_from_exception(exc)
    assert status_code == fastapi.status.HTTP_418_IM_A_TEAPOT
    assert model.message == "teapot"
