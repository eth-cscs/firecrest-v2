# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime
from typing import Dict, List

# configs
from firecrest.config import HPCCluster

# models
from lib.models import CamelModel
from lib.scheduler_clients.slurm.models import (
    SlurmNode,
    SlurmPartitions,
    SlurmReservations,
)
from lib.scheduler_clients.pbs.models import PbsNode, PbsPartition, PbsReservation


class GetLiveness(CamelModel):
    healthcheck_runs: Dict[str, datetime] = None
    last_update: int = None


class GetSystemsResponse(CamelModel):
    systems: List[HPCCluster]


class GetNodesResponse(CamelModel):
    nodes: List[SlurmNode | PbsNode]


class GetPartitionsResponse(CamelModel):
    partitions: List[SlurmPartitions | PbsPartition]


class GetReservationsResponse(CamelModel):
    reservations: List[SlurmReservations | PbsReservation]


class PosixIdentified(CamelModel):
    id: str
    name: str


class UserInfoResponse(CamelModel):
    user: PosixIdentified
    group: PosixIdentified
    groups: List[PosixIdentified]
