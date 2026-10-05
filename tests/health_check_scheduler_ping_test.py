# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from firecrest.status.health_check.checks.health_check_scheduler import ping_is_up


def test_ping_is_up_legacy_pinged_shape():
    # data_parser < v0.0.45 (and `scontrol ping` on the CLI client)
    assert ping_is_up({"hostname": "ctl", "pinged": "UP", "mode": "primary"})
    assert not ping_is_up({"hostname": "ctl", "pinged": "DOWN", "mode": "primary"})


def test_ping_is_up_responding_shape():
    # data_parser >= v0.0.45 (Slurm 26.05): ``responding``/``primary`` only
    assert ping_is_up({"hostname": "ctl", "responding": True, "primary": True})
    assert not ping_is_up({"hostname": "ctl", "responding": False, "primary": True})


def test_ping_is_up_overloaded_shape_prefers_responding():
    # data_parser v0.0.44 (Slurm 25.11) emits both, ``pinged`` deprecated
    assert ping_is_up({"pinged": "DOWN", "responding": True})
    assert not ping_is_up({"pinged": "UP", "responding": False})


def test_ping_is_up_missing_fields_is_down():
    assert not ping_is_up({"hostname": "ctl"})
    assert not ping_is_up({"pinged": None})
