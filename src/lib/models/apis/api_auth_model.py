# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum

from fastapi import HTTPException, status

# models
from lib.models.base_model import CamelModel


class ApiAuthType(str, Enum):
    user = "user"
    service_account = "service-account"


class ApiAuthModel(CamelModel):
    type: ApiAuthType
    active: bool = False
    username: str = None

    @staticmethod
    def build_from_oidc_decoded_token(
        decoded_token: dict, username_claim: str = "preferred_username"
    ):
        if username_claim not in decoded_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Authentication token '{username_claim}' claim is missing",
            )
        username = decoded_token.get(username_claim)

        if "email" not in decoded_token:
            return ApiAuthServiceAccount(
                type=ApiAuthType.service_account,
                username=username,
                active=True,
            )
        return ApiAuthUser(
            type=ApiAuthType.user,
            username=username,
            email=decoded_token.get("email"),
            first_name=decoded_token.get("given_name"),
            active=True,
        )

    def is_active(self):
        return self.active


class ApiAuthServiceAccount(ApiAuthModel):
    pass


class ApiAuthUser(ApiAuthModel):
    email: str = None
    first_name: str = None
    last_name: str = None
