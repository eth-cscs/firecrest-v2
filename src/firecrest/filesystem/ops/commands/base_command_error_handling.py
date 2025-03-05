# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from fastapi import HTTPException, status


class FilesystemError(HTTPException):
    pass


class FilesystemConflict(HTTPException):
    pass


class PermissionError(HTTPException):
    pass


class OperationNotPermitted(HTTPException):
    pass


class CommandExecutionError(HTTPException):
    pass


class BaseCommandErrorHandling:

    def error_handling(self, stderr: str, exit_status: int):

        error_mess = f"Remote process failed with exit status:{exit_status}"
        if len(stderr) > 0:
            error_mess += f" and error message:{stderr.strip()}"

        if exit_status == 124:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=error_mess
            )

        if "No such file or directory" in stderr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=error_mess
            )
        if "Permission denied" in stderr:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=error_mess
            )
        if "Operation not permitted" in stderr:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=error_mess
            )
        if "File exists" in stderr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_mess
            )
        if "invalid user" in stderr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_mess
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_mess
        )
