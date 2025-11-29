import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import pytest
import tomlkit

from ttr.src.ttr import TestCases
from ttr.src.ttr import main as ttr_main


@pytest.fixture()
def tmp_test_data_dir(tmpdir_factory):
    return Path(tmpdir_factory.mktemp("ttr_test_rootdir"))


@pytest.fixture()
def minimal_raw_config():
    return tomlkit.parse(
        """
        [general]
        [modifs]
        [cases.alaro]
        """
    )


@pytest.fixture()
def config_path(minimal_raw_config, tmp_test_data_dir):
    config_path = tmp_test_data_dir / "config.toml"
    with open(config_path, "w") as config_file:
        tomlkit.dump(minimal_raw_config, config_file)
    return config_path


@dataclass
class DummyArgs:
    config_file = None
    verbose = False
    dry = False
    run = False
    list = False
    prepare_binaries = False


@pytest.fixture()
def args(config_path):
    args = DummyArgs
    args.config_file = config_path

    return args


# -------------------------------------------------------------
# resolve_selection
# -------------------------------------------------------------
def test_resolve_selection_basic(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "tag_")

    tc = TestCases(args)

    tc.cases = {"A": {}, "B": {}}
    definitions = {"general": {}, "cases": tc.cases}

    sel = tc.resolve_selection(definitions)
    assert set(sel) == {"A", "B"}


def test_resolve_selection_with_subtags(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "tag_")

    tc = TestCases(args)
    tc.cases = {"X": {"host": "Xhost"}, "Y": {}}
    definitions = {
        "general": {
            "selection": ["X"],
            "subtags": [{"a": ["foo", "bar"]}],
        },
        "cases": tc.cases,
    }

    sel = tc.resolve_selection(definitions)

    assert "aX" in sel
    assert "aX" in tc.cases
    assert tc.cases["aX"]["subtag"] == "a"
    assert "foo" in tc.cases["aX"]["extra"]
    assert "bar" in tc.cases["aX"]["extra"]


# -------------------------------------------------------------
# get_tactus_version
# -------------------------------------------------------------
def test_get_tactus_version(monkeypatch, args):
    filedata = b"""
        [tool.poetry.dependencies.deode]
        tag = "feature/testbranch"
    """
    monkeypatch.setattr("builtins.open", mock.mock_open(read_data=filedata))

    args.config_file = None
    tc = TestCases(args)
    version = tc.get_tactus_version()

    assert version.startswith("feature_testbranch_")


# -------------------------------------------------------------
# prepare
# -------------------------------------------------------------
def test_prepare_valid_hosts(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    tc = TestCases(args)

    tc.selection = ["A", "B"]
    tc.cases = {
        "A": {"host": "hostA"},
        "B": {"host": "hostB"},
    }

    hosts = tc.prepare()
    assert hosts == ["hostA", "hostB"]


# -------------------------------------------------------------
# get_cmd
# -------------------------------------------------------------
def test_get_cmd(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    tc = TestCases(args)

    with tempfile.TemporaryDirectory() as td:
        tc.test_dir = td
        modifs = mock.Mock()
        modifs.save_as = mock.Mock()

        cmd = tc.get_cmd("case1", modifs, base="B", extra=["foo.toml"])

        modifs.save_as.assert_called_once()
        assert cmd[0] == "case"
        assert "foo.toml" in cmd
        assert any("modifs_case1.toml" in part for part in cmd)


# -------------------------------------------------------------
# list
# -------------------------------------------------------------
def test_list(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    args.list = True
    tc = TestCases(args)
    tc.list()


# -------------------------------------------------------------
# expand_tests
# -------------------------------------------------------------
def test_expand_tests(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    args.list = True
    tc = TestCases(args)
    tc.expand_tests({"ial": {"bindir": "foo", "tests": {}}})


# -------------------------------------------------------------
# create
# -------------------------------------------------------------
def test_create_and_configure(monkeypatch, args, tmp_test_data_dir):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    tc = TestCases(args)
    os.chdir(tmp_test_data_dir)
    tc.create()
    # tactus_main should be mocked here
    tc.configure()


# -------------------------------------------------------------
# get_binaries
# -------------------------------------------------------------
def test_get_binaries(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    args.dry = True
    tc = TestCases(args)
    tc.ial = {"ial_hash": "foo", "bindir": "foo", "build_tar_path": "foo"}
    tc.get_binaries()


# -------------------------------------------------------------
# main
# -------------------------------------------------------------
def test_main(monkeypatch):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    ttr_main(["-d"])


# -------------------------------------------------------------
# update_hostname
# -------------------------------------------------------------
def test_update_hostname(monkeypatch, args):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda: "x_")
    tc = TestCases(args)
    tc.cases = {
        "foo": {
            "host": "baar",
        }
    }
    hostnames = [{"baar": {"config_name": "x", "domain_name": "y"}}]
    tc.update_hostnames(hostnames)
