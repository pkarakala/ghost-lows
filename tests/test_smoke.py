import importlib

import pytest

import ghostlows

SUBPACKAGES = ["io", "metrics", "sim", "faults", "alarms", "bench", "retro"]


def test_version():
    assert ghostlows.__version__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name):
    assert importlib.import_module(f"ghostlows.{name}").__doc__
