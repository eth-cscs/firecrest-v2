# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from lib.scheduler_clients.slurm.cli_commands.sacctmgr_accounts import (
    SacctmgrAccountsCommand,
)
from lib.scheduler_clients.slurm.cli_commands.sacctmgr_default_account import (
    SacctmgrDefaultAccountCommand,
)


def test_accounts_command_uses_parsable_output():
    # Without -P, sacctmgr truncates names wider than the column ("project-a+")
    command = SacctmgrAccountsCommand("test-user").get_command()
    assert command == "sacctmgr show assoc user='test-user' format=account -n -P"


def test_default_account_command_uses_parsable_output():
    command = SacctmgrDefaultAccountCommand("test-user").get_command()
    assert command == "sacctmgr show user 'test-user' format=defaultaccount -n -P"


def test_accounts_long_names_are_kept():
    accounts = SacctmgrAccountsCommand("test-user").parse_output(
        "project-account-1\nproject-account-2\n", ""
    )
    assert accounts == ["project-account-1", "project-account-2"]


def test_accounts_one_entry_per_account():
    # sacctmgr lists one association row per partition (and cluster)
    accounts = SacctmgrAccountsCommand("test-user").parse_output(
        "root\nproject-account-1\nproject-account-1\nproject-account-2\n"
        "project-account-1\n",
        "",
    )
    assert accounts == ["root", "project-account-1", "project-account-2"]


def test_accounts_empty_output():
    assert SacctmgrAccountsCommand("test-user").parse_output("\n", "") is None
