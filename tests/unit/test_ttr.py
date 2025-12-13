import os
from dataclasses import dataclass
from pathlib import Path

import pytest
import tomlkit
from deode.logs import logger

from ttr.src import ttr
from ttr.src.ttr import TestCases
from ttr.src.ttr import main as ttr_main

MESSAGES = []


def sink(msg):
    MESSAGES.append(msg)


@pytest.fixture(scope="session")
def tmp_test_data_dir(tmpdir_factory):
    return Path(tmpdir_factory.mktemp("ttr_test_rootdir"))


@pytest.fixture()
def minimal_raw_config():
    return tomlkit.parse(
        """
        [general]
        [modifs]
        [cases.alaro]
        [domain]
          name = "foo"
        [cases.alaro_target]
          host = "alaro"
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


def dump_toml(self):  # noqa ARG001
    config = tomlkit.parse(
        """
            [domain]
              name = "foo"
            """
    )
    with open("x_configs/foo.toml", "w") as config_file:
        tomlkit.dump(config, config_file)


@pytest.fixture()
def _mockers(monkeypatch, session_mocker):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda self: "x_")  # noqa ARG001
    session_mocker.patch("deode.__main__.main", new=dump_toml)


# -------------------------------------------------------------
# resolve_selection
# -------------------------------------------------------------
@pytest.mark.usefixtures("_mockers")
def test_resolve_selection_basic(args):
    tc = TestCases(args)

    tc.cases = {"A": {}, "B": {}}
    definitions = {"general": {}, "cases": tc.cases}

    sel = tc.resolve_selection(definitions)
    assert set(sel) == {"A", "B"}


# -------------------------------------------------------------
# resolve_selection with subtags
# -------------------------------------------------------------
def test_get_tag_digit(args, monkeypatch):
    monkeypatch.setattr(TestCases, "get_tactus_version", lambda self: "0_")  # noqa ARG001
    with pytest.raises(ValueError, match=r"The tag cannot start with an integer. tag=0_"):
        TestCases(args)


# -------------------------------------------------------------
# resolve_selection with compiler
# -------------------------------------------------------------
def test_resolve_selection_with_compiler(args):
    tc = TestCases(args)
    tc.cases = {"X": {"host": "Xhost"}, "Y": {}}
    definitions = {
        "general": {
            "selection": ["X"],
            "compiler": {
                "a": {"active": True, "extra": ["foo", "bar"]},
                "b": {"active": True, "exclude": ["Y"]},
                "c": {"active": False},
            },
        },
        "cases": tc.cases,
    }

    sel = tc.resolve_selection(definitions)

    assert "aX" in sel
    assert "bY" not in sel
    assert "c" not in sel
    assert "aX" in tc.cases
    assert tc.cases["aX"]["subtag"] == "a"
    assert "foo" in tc.cases["aX"]["extra"]
    assert "bar" in tc.cases["aX"]["extra"]
    assert "c" not in tc.cases


# -------------------------------------------------------------
# get_tactus_version
# -------------------------------------------------------------
@pytest.mark.parametrize("param", ["tag", "branch", "rev", "Unknown"])
def test_get_tactus_version(monkeypatch, args, param):
    monkeypatch.setattr(
        "tomli.load",
        lambda _: {
            "tool": {
                "poetry": {"dependencies": {"deode": {param: f"{param}/testbranch"}}}
            }
        },
    )

    args.config_file = None
    tc = TestCases(args)
    version = tc.get_tactus_version()
    assert version.startswith(param)


# -------------------------------------------------------------
# prepare
# -------------------------------------------------------------
def test_prepare_valid_hosts(args):
    tc = TestCases(args)
    tc.selection = ["A", "B"]
    tc.cases = {
        "A": {"host": "hostA"},
        "B": {"host": "hostB"},
    }

    hosts = tc.prepare()
    assert hosts == ["hostA", "hostB"]


# -------------------------------------------------------------
# invalid hosts
# -------------------------------------------------------------
def test_prepare_invalid_hosts(args):
    tc = TestCases(args)
    tc.selection = ["X"]
    tc.cases = {"A": {}}

    with pytest.raises(KeyError, match=r"The case.*"):
        tc.prepare()


# -------------------------------------------------------------
# expand_tests
# -------------------------------------------------------------
@pytest.mark.usefixtures("_mockers")
def test_expand_tests(args):
    tc = TestCases(args)
    tc.expand_tests({"ial": {"bindir": "foo", "tests": {"gnu": {"dp": ["foo", "baar"]}}}})

    assert "baar_gnu_dp" in tc.cases


# -------------------------------------------------------------
# list
# -------------------------------------------------------------
def test_list(args):
    args.list = True
    args.verbose = True
    tc = TestCases(args)

    logger_id = logger.add(sink)
    tc.list()
    assert any("alaro" in m for m in MESSAGES)
    logger.remove(logger_id)


# -------------------------------------------------------------
# get_binaries
# -------------------------------------------------------------
def test_get_binaries(args, tmp_test_data_dir):
    Path(f"{tmp_test_data_dir}/foo-sp--gnu-.tar").touch()
    os.environ["DEODE_HOST"] = "atos_bologna"
    args.dry = True
    tc = TestCases(args)
    tc.ial = {
        "ial_hash": "foo",
        "build_tar_path": tmp_test_data_dir,
        "user_binary_path": tmp_test_data_dir,
    }
    tc.get_binaries()
    assert os.path.isdir(f"{tmp_test_data_dir}/foo/gnu/R32")
    os.environ.pop("DEODE_HOST")


# -------------------------------------------------------------
# update_hostname
# -------------------------------------------------------------
def test_update_hostname(args):
    tc = TestCases(args)
    tc.cases = {
        "foo": {
            "host": "baar",
        }
    }
    hostnames = {"baar": {"config_name": "x", "domain_name": "y"}}
    tc.update_hostnames(hostnames)
    assert tc.cases["foo"]["hostname"] == hostnames["baar"]["config_name"]
    assert tc.cases["foo"]["hostdomain"] == hostnames["baar"]["domain_name"]


# -------------------------------------------------------------
# create and configure
# -------------------------------------------------------------
@pytest.mark.usefixtures("_mockers")
def test_create_and_configure(monkeypatch, args, tmp_test_data_dir):
    monkeypatch.setattr(ttr, "tactus_main", dump_toml)
    tc = TestCases(args)
    basedir = os.getcwd()
    os.chdir(tmp_test_data_dir)
    tc.create()
    tc.configure(config_hosts=True, cmds=["foo"])
    os.chdir(basedir)


# -------------------------------------------------------------
# start
# -------------------------------------------------------------
def test_start(args):
    tc = TestCases(args)
    tc.dry = True
    tc.mode = "task"
    tc.cmds = ["foo"]
    tc.cases = {"foo": {"config_name": "bar", "tasks": ["foo"]}}
    tc.test_dir = "foo"
    tc.start()


# -------------------------------------------------------------
# main
# -------------------------------------------------------------
@pytest.mark.usefixtures("_mockers")
def test_main(monkeypatch, tmp_test_data_dir, args):
    basedir = os.getcwd()
    os.chdir(tmp_test_data_dir)
    monkeypatch.setattr(ttr, "tactus_main", dump_toml)
    ttr_main(["-d", "-c", str(args.config_file)])
    os.chdir(basedir)
