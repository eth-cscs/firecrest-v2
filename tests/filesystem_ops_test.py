# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from importlib import resources as impresources
from firecrest.filesystem.ops.models import File
from tests import mocked_ssh_outputs
import pytest
import json

from tests.mock_ssh_client import MockedCommand


def load_ssh_output(file: str):
    output_file = impresources.files(mocked_ssh_outputs) / file
    with output_file.open("rb") as output:
        return json.load(output)


@pytest.fixture(scope="module")
def mocked_ssh_ls_output():
    return load_ssh_output("ssh_ls_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_ls_recursive_output():
    return load_ssh_output("ssh_ls_recursive_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_ls_folllow_output():
    return load_ssh_output("ssh_ls_follow_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_ls_hidden_output():
    return load_ssh_output("ssh_ls_with_hidden_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_checksum_output():
    return load_ssh_output("ssh_checksum_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_file_output():
    return load_ssh_output("ssh_file_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_head_output():
    return load_ssh_output("ssh_head_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_dd_output():
    return load_ssh_output("ssh_dd_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_dd_with_size_output():
    return load_ssh_output("ssh_dd_command_with_size.json")

@pytest.fixture(scope="module")
def mocked_ssh_tail_output():
    return load_ssh_output("ssh_tail_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_chmod_output():
    return load_ssh_output("ssh_chmod_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_chown_output():
    return load_ssh_output("ssh_chown_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_stat_output():
    return load_ssh_output("ssh_stat_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_mkdir_output():
    return load_ssh_output("ssh_mkdir_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_mkdir_output_parent():
    return load_ssh_output("ssh_mkdir_command_parent.json")


@pytest.fixture(scope="module")
def mocked_ssh_mkdir_not_found_error():
    return load_ssh_output("ssh_mkdir_command_not_found_error.json")


@pytest.fixture(scope="module")
def mocked_ssh_mkdir_permission_error():
    return load_ssh_output("ssh_mkdir_command_permission_error.json")


@pytest.fixture(scope="module")
def mocked_ssh_mkdir_error():
    return load_ssh_output("ssh_mkdir_command_error.json")


@pytest.fixture(scope="module")
def mocked_ssh_rm_output():
    return load_ssh_output("ssh_rm_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_symlink_output():
    return load_ssh_output("ssh_symlink_command.json")


@pytest.fixture(scope="module")
def mocked_ssh_tar_output():
    return load_ssh_output("ssh_tar_command.json")


async def test_ls_command(client, ssh_client, mocked_ssh_ls_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_ls_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/ls?path={path}".format(path="/home")
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert len(response.json()["output"]) == 4


async def test_ls_recursive_command(client, ssh_client, mocked_ssh_ls_recursive_output):

    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_ls_recursive_output)]
    ):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/ls?path={path}&recursive=true".format(
                path="/home/test1"
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert len(response.json()["output"]) == 2


async def test_ls_hidden_command(client, ssh_client, mocked_ssh_ls_hidden_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_ls_hidden_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/ls?path={path}&showHidden=true".format(
                path="/home"
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert len(response.json()["output"]) == 4


async def test_ls_dereference_command(client, ssh_client, mocked_ssh_ls_folllow_output):

    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_ls_folllow_output)]
    ):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/ls?path={path}&recursive=true&dereference=true".format(
                path="/home/test1"
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert len(response.json()["output"]) == 8
        assert response.json()["output"][7]["name"] == "b/tt_link/file"


async def test_mkdir_command(client, ssh_client, mocked_ssh_mkdir_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_mkdir_output)]):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/mkdir", json={"path": "/home/dir1"}
        )
        assert response.status_code == 201
        assert File(**response.json()["output"]) is not None


async def test_mkdir_command_parent(client, ssh_client, mocked_ssh_mkdir_output_parent):

    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_mkdir_output_parent)]
    ):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/mkdir",
            json={"path": "/home/dir1", "parent": True},
        )
        assert response.status_code == 201
        assert File(**response.json()["output"]) is not None


async def test_mkdir_command_permission_error(
    client, ssh_client, mocked_ssh_mkdir_permission_error
):

    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_mkdir_permission_error)]
    ):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/mkdir", json={"path": "/home/test"}
        )
        assert response.status_code == 403


async def test_mkdir_command_not_found_error(
    client, ssh_client, mocked_ssh_mkdir_not_found_error
):

    async with ssh_client.mocked_output(
        [MockedCommand(**mocked_ssh_mkdir_not_found_error)]
    ):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/mkdir",
            json={"path": "/home/tmp/dir2/subdir"},
        )
        assert response.status_code == 404


async def test_mkdir_command_generic_error(client, ssh_client, mocked_ssh_mkdir_error):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_mkdir_error)]):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/mkdir", json={"path": "/home"}
        )
        assert response.status_code == 400


async def test_checksum_command(client, ssh_client, mocked_ssh_checksum_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_checksum_output)]):
        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/checksum?path={path}".format(
                path="/home/README.md"
            )
        )
        assert response.status_code == 200
        response_json = response.json()
        assert response_json is not None
        assert (
            response_json["output"]["checksum"]
            == "6d4c4f9ac2c9228c274dea099d83141d8b8cd1aa8902319d6d8313c767a7f93c"
        )


async def test_checksum_command_error(client, ssh_client, mocked_ssh_checksum_output):
    mocked_ssh_checksum_output["exit_code"] = 1
    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_checksum_output)]):
        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/checksum?path={path}".format(
                path="/home/README.md"
            )
        )
        assert response.status_code == 500
        response_json = response.json()
        assert response_json is not None


async def test_file_command(client, ssh_client, mocked_ssh_file_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_file_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/file?path={path}".format(
                path="/home/README.md"
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["output"] == mocked_ssh_file_output["stdout"]


async def test_dd_command(client, ssh_client, mocked_ssh_dd_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_dd_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/view?path={path}".format(
                path="/home/readme.txt"
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["output"] == mocked_ssh_dd_output["stdout"]

async def test_dd_command_with_size(client, ssh_client, mocked_ssh_dd_with_size_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_dd_with_size_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/view?path={path}&size={size}".format(
                path="/home/readme.txt", size=5
            )
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["output"] == mocked_ssh_dd_with_size_output["stdout"]


async def test_head_command(client, ssh_client, mocked_ssh_head_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_head_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/head?path={path}".format(path="/home")
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["output"] == {
            "content": "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n",
            "contentType": "lines",
            "startPosition": 0,
            "endPosition": 10,
        }

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/head?path={path}&lines={lines}&bytes={bytes}".format(
                path="/home", lines=10, bytes=10
            )
        )
        assert response.status_code == 400
        assert response.json() is not None
        assert (
            response.json()["message"]
            == "Only one of `bytes` or `lines` can be specified."
        )


async def test_tail_command(client, ssh_client, mocked_ssh_tail_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_tail_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/tail?path={path}".format(path="/home")
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()["output"] == {
            "content": "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n",
            "contentType": "lines",
            "startPosition": 10,
            "endPosition": -1,
        }

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/tail?path={path}&lines={lines}&bytes={bytes}".format(
                path="/home", lines=10, bytes=10
            )
        )
        assert response.status_code == 400
        assert response.json() is not None
        assert (
            response.json()["message"]
            == "Only one of `bytes` or `lines` can be specified."
        )


async def test_chmod_command(client, ssh_client, mocked_ssh_chmod_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_chmod_output)]):

        response = client.put(
            "/filesystem/cluster-slurm-ssh/ops/chmod",
            json={"path": "/home/chmod-test/test.txt", "mode": "777"},
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert File(**response.json()["output"]) is not None


async def test_chown_command(client, ssh_client, mocked_ssh_chown_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_chown_output)]):

        response = client.put(
            "/filesystem/cluster-slurm-ssh/ops/chown",
            json={
                "path": "/home/chown-test/test.txt",
                "user": "test1",
                "group": "test1",
            },
        )
        assert response.status_code == 200
        assert response.json() is not None
        assert File(**response.json()["output"]) is not None


async def test_stat_command(client, ssh_client, mocked_ssh_stat_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_stat_output)]):

        response = client.get(
            "/filesystem/cluster-slurm-ssh/ops/stat?path={path}&dereference=true".format(
                path="/home/test1/data.big"
            )
        )
        assert response.status_code == 200
        response_data = response.json()
        assert response_data is not None
        print(response_data["output"])
        assert len(list(response_data["output"])) == 10


async def test_rm_command(client, ssh_client, mocked_ssh_rm_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_rm_output)]):

        response = client.delete(
            "/filesystem/cluster-slurm-ssh/ops/rm?path={path}".format(
                path="/home/file-to-delete"
            )
        )
        assert response.status_code == 204


async def test_symlink_command(client, ssh_client, mocked_ssh_symlink_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_symlink_output)]):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/symlink",
            json={
                "path": "/home/symlink-test/test.txt",
                "link_path": "/home/symlink-test/link.txt",
            },
        )
        assert response.status_code == 201
        assert response.json() is not None
        file = File(**response.json()["output"])
        assert file is not None
        assert file.link_target is not None


async def test_tar_compress_command(client, ssh_client, mocked_ssh_tar_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_tar_output)]):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/compress",
            json={
                "source_path": "/home/files/",
                "target_path": "/home/compressed.tar.gz",
            },
        )
        assert response.status_code == 204


async def test_tar_compress_with_pattern_command(client, ssh_client, mocked_ssh_tar_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_tar_output)]):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/compress",
            json={
                "source_path": "/home/files/",
                "target_path": "/home/compressed.tar.gz",
                "match_pattern": "./[ab].*\\.txt"
            },
        )
        assert response.status_code == 204


async def test_tar_extract_command(client, ssh_client, mocked_ssh_tar_output):

    async with ssh_client.mocked_output([MockedCommand(**mocked_ssh_tar_output)]):

        response = client.post(
            "/filesystem/cluster-slurm-ssh/ops/extract",
            json={
                "source_path": "/home/compressed.tar.gz",
                "target_path": "/home/",
            },
        )
        assert response.status_code == 204
