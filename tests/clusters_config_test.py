# Add src folder to python paths
import os
import sys
import pytest


from firecrest.config import SchedulerType, get_settings, Settings

sys.path.append(os.path.abspath("./src/"))


@pytest.fixture(scope="module")
def app_settings():
    return get_settings()


async def test_settings(app_settings: Settings):

    assert app_settings is not None
    assert len(app_settings.clusters) == 2
    assert app_settings.clusters[0].name == "cluster-slurm-api"
    assert app_settings.clusters[0].scheduler is not None
    assert app_settings.clusters[0].scheduler.type == SchedulerType.slurm

    assert app_settings.storage is not None
