# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import shlex

import pytest

from firecrest.filesystem.ops.commands.base64_command import Base64Command
from firecrest.filesystem.ops.commands.checksum_command import ChecksumCommand
from firecrest.filesystem.ops.commands.chmod_command import ChmodCommand
from firecrest.filesystem.ops.commands.chown_command import ChownCommand
from firecrest.filesystem.ops.commands.dd_command import DdCommand
from firecrest.filesystem.ops.commands.file_command import FileCommand
from firecrest.filesystem.ops.commands.head_command import HeadCommand
from firecrest.filesystem.ops.commands.ls_base_command import LsBaseCommand
from firecrest.filesystem.ops.commands.mkdir_command import MkdirCommand
from firecrest.filesystem.ops.commands.rm_command import RmCommand
from firecrest.filesystem.ops.commands.stat_command import StatCommand
from firecrest.filesystem.ops.commands.symlink_command import SymlinkCommand
from firecrest.filesystem.ops.commands.tail_command import TailCommand
from firecrest.filesystem.ops.commands.tar_command import TarCommand
from firecrest.filesystem.transfer.router import (
    _build_script as build_filesystem_job_script,
)
from lib.datatransfers.datatransfer_base import (
    _build_script as build_datatransfer_job_script,
)
from tests.mock_ssh_client import MockedCommand

# A file name any user can create on a shared filesystem. Interpolated
# between single quotes, it closes them and runs `touch pwned` as whoever
# operates on the file next.
HOSTILE_NAME = "x'; touch pwned; echo '$(id)`id`"
HOSTILE_PATH = f"/home/user/{HOSTILE_NAME}"


def shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def assert_single_argument(command: str):
    tokens = shell_tokens(command)
    assert "touch" not in tokens
    assert any(HOSTILE_NAME in token for token in tokens)


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(Base64Command(path=HOSTILE_PATH), id="base64"),
        pytest.param(Base64Command(path=HOSTILE_PATH, decode=True), id="base64-decode"),
        pytest.param(ChecksumCommand(target_path=HOSTILE_PATH), id="checksum"),
        pytest.param(ChmodCommand(target_path=HOSTILE_PATH, mode="755"), id="chmod"),
        pytest.param(
            ChownCommand(target_path=HOSTILE_PATH, owner="user", group="group"),
            id="chown",
        ),
        pytest.param(
            DdCommand(target_path=HOSTILE_PATH, size=5, size_limit=5), id="dd"
        ),
        pytest.param(FileCommand(target_path=HOSTILE_PATH), id="file"),
        pytest.param(HeadCommand(target_path=HOSTILE_PATH), id="head"),
        pytest.param(LsBaseCommand(target_path=HOSTILE_PATH), id="ls"),
        pytest.param(MkdirCommand(target_path=HOSTILE_PATH), id="mkdir"),
        pytest.param(RmCommand(target_path=HOSTILE_PATH), id="rm"),
        pytest.param(StatCommand(target_path=HOSTILE_PATH), id="stat"),
        pytest.param(
            SymlinkCommand(target_path=HOSTILE_PATH, link_path=HOSTILE_PATH),
            id="symlink",
        ),
        pytest.param(TailCommand(target_path=HOSTILE_PATH), id="tail"),
        pytest.param(
            TarCommand(f"/home/{HOSTILE_NAME}/data", HOSTILE_PATH), id="compress"
        ),
        pytest.param(
            TarCommand(
                HOSTILE_PATH, HOSTILE_PATH, operation=TarCommand.Operation.extract
            ),
            id="extract",
        ),
    ],
)
def test_path_is_passed_as_a_single_argument(command):
    assert_single_argument(command.get_command())


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(ChmodCommand(target_path="/home/f", mode=HOSTILE_NAME), id="mode"),
        pytest.param(
            ChownCommand(target_path="/home/f", owner=HOSTILE_NAME, group="group"),
            id="owner",
        ),
        pytest.param(
            ChownCommand(target_path="/home/f", owner="user", group=HOSTILE_NAME),
            id="group",
        ),
    ],
)
def test_other_string_arguments_are_quoted(command):
    assert_single_argument(command.get_command())


def test_compress_with_pattern_quotes_the_inner_shell_script():
    command = TarCommand(
        f"/home/{HOSTILE_NAME}/data/", HOSTILE_PATH, match_pattern=HOSTILE_NAME
    )

    outer = shell_tokens(command.get_command())
    assert outer[:4] == ["timeout", "5", "bash", "-c"]
    assert len(outer) == 5
    assert_single_argument(outer[4])


async def test_rm_command_with_quote_in_path(client, ssh_client):
    # The mock matches by substring, so an unquoted path never reaches it.
    mocked = MockedCommand(
        stdout="",
        stderr="",
        command="rm -r --interactive=never -- "
        "'/home/user/x'\"'\"'; touch pwned; echo '\"'\"'$(id)`id`'"
    )

    async with ssh_client.mocked_output([mocked]):
        response = client.delete(
            "/filesystem/cluster-slurm-ssh/ops/rm", params={"path": HOSTILE_PATH}
        )
        assert response.status_code == 204


# Job scripts double-quote or leave some paths bare, so `$(...)` and
# backticks must be covered as well as a closing quote.
HOSTILE_JOB_PATH = "/home/user/x'$(touch pwned)`touch pwned`\"; touch pwned"


def assert_only_quoted(script: str, value: str):
    quoted = shlex.quote(value)
    assert quoted in script
    assert "pwned" not in script.replace(quoted, "")


@pytest.mark.parametrize(
    "script, parameters",
    [
        ("job_move.sh", {"source_path": HOSTILE_JOB_PATH, "target_path": HOSTILE_JOB_PATH}),
        ("job_copy.sh", {"source_path": HOSTILE_JOB_PATH, "target_path": HOSTILE_JOB_PATH}),
        ("job_delete.sh", {"path": HOSTILE_JOB_PATH}),
        ("job_extract.sh", {"source_path": HOSTILE_JOB_PATH, "target_path": HOSTILE_JOB_PATH}),
        (
            "job_compress.sh",
            {
                "source_dir": HOSTILE_JOB_PATH,
                "source_file": HOSTILE_JOB_PATH,
                "target_path": HOSTILE_JOB_PATH,
            },
        ),
        (
            "job_compress.sh",
            {
                "source_dir": HOSTILE_JOB_PATH,
                "target_path": HOSTILE_JOB_PATH,
                "match_pattern": HOSTILE_JOB_PATH,
            },
        ),
    ],
)
def test_filesystem_job_scripts_quote_paths(script, parameters):
    assert_only_quoted(build_filesystem_job_script(script, parameters), HOSTILE_JOB_PATH)


@pytest.mark.parametrize(
    "script, parameters",
    [
        ("job_s3_downloader.sh", {"target_path": HOSTILE_JOB_PATH}),
        ("job_s3_uploader_multipart.sh", {"F7T_MP_INPUT_FILE": HOSTILE_JOB_PATH}),
        ("job_streamer.sh", {"operation": "send", "target_path": HOSTILE_JOB_PATH}),
        ("job_streamer.sh", {"operation": "receive", "target_path": HOSTILE_JOB_PATH}),
        (
            "job_wormhole_receive.sh",
            {"wormhole_code": HOSTILE_JOB_PATH, "target_path": HOSTILE_JOB_PATH},
        ),
        (
            "job_wormhole_send.sh",
            {"wormhole_code": HOSTILE_JOB_PATH, "source": HOSTILE_JOB_PATH},
        ),
    ],
)
def test_datatransfer_job_scripts_quote_paths(script, parameters):
    assert_only_quoted(build_datatransfer_job_script(script, parameters), HOSTILE_JOB_PATH)


def test_job_scripts_keep_html_special_characters_in_paths():
    # Jinja's HTML autoescape used to turn `&` into `&amp;` and `'` into `&#39;`.
    script = build_filesystem_job_script("job_delete.sh", {"path": "/home/R&D's data"})

    assert "'/home/R&D'\"'\"'s data'" in script
    assert "&amp;" not in script
