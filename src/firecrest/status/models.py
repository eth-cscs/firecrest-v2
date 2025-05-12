# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime
from typing import Dict, List, Optional

# configs
from firecrest.config import HPCCluster, Storage

# models
from lib.models import CamelModel
from lib.scheduler_clients.slurm.models import (
    SlurmNode,
    SlurmPartitions,
    SlurmReservations,
)


class GetLiveness(CamelModel):
    healthcheck_runs: Dict[str, datetime] = None
    last_update: int = None


class GetSystemsResponse(CamelModel):
    systems: List[HPCCluster]
    storage: Optional[Storage] = None


class GetNodesResponse(CamelModel):
    nodes: List[SlurmNode]


class GetPartitionsResponse(CamelModel):
    partitions: List[SlurmPartitions]


class GetReservationsResponse(CamelModel):
    reservations: List[SlurmReservations]


class PosixIdentified(CamelModel):
    id: str
    name: str


class UserInfoResponse(CamelModel):
    user: PosixIdentified
    group: PosixIdentified
    groups: List[PosixIdentified]
