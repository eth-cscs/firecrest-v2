# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional

from pydantic import AliasChoices, Field
from lib.models.base_model import CamelModel


class FilesystemRequestBase(CamelModel):
    path: Optional[str] = Field(
        validation_alias=AliasChoices("sourcePath", "source_path"),
        example="/home/user/dir"
    )
