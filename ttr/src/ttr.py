"""Tactus-test-runner main driver."""
import argparse
import contextlib
import copy
import glob
import os
from pathlib import Path

import tomli
from deode.__main__ import main as tactus_main
from deode.config_parser import ConfigPaths, GeneralConstants, ParsedConfig
from deode.fullpos import flatten_list
from deode.general_utils import merge_dicts
from deode.logs import logger


class TestCases:
    """Class to orchestrate the tests."""

    def __init__(self, args):
        """Construct the object.

        Args:
            args (argsparse objectl): Command line arguments

        """
        ConfigPaths.CONFIG_DATA_SEARCHPATHS.insert(0, os.path.join(os.getcwd()))

        definitions = {"general": {}, "modifs": {}}
        if args.config_file is not None:
            self.config = ParsedConfig.from_file(args.config_file, json_schema={})
            try:
                definitions = self.config.expand_macros().dict()
            except KeyError:
                definitions = self.config.dict()

        self.verbose = args.verbose
        self.cases = definitions.get("cases", {})
        self.extra = definitions["general"].get("extra", [])
        if "tag" not in definitions["general"]:
            definitions["general"]["tag"] = self.get_tactus_version()
        self.tag = definitions["general"].get("tag")
        self.dry = args.dry if args.dry else definitions["general"].get("dry", False)
        self.modifs = definitions["modifs"]
        self.test_dir = definitions.get("test_dir", f"{self.tag}configs")
        self.ial = definitions.get("ial", {})
        self.selection = self.resolve_selection(definitions)

        if args.config_file is not None:
            with contextlib.suppress(KeyError):
                if definitions["ial"].get("active", False):
                    self.expand_tests(definitions)

        logger.info("Using config file: {}", args.config_file)
        logger.info(" tag: {}", self.tag)

    def resolve_selection(self, definitions):
        """Resolve the selections.

        Arguments:
            definitions (dict) : Configuration

        Returns:
            selection (list) : List of selected configurations
        """
        selection = definitions["general"].get("selection", list(self.cases))

        # Handle subtags and update selection accordingly
        with contextlib.suppress(KeyError):
            subtags = definitions["general"]["subtags"]
            subtag_selection = []
            for key in subtags:
                tag, v = key.popitem()
                for sel in selection:
                    subtag = f"{tag}{sel}"
                    x = copy.deepcopy(self.cases[sel])
                    if "base" not in x:
                        x["base"] = sel
                    if "host" in x:
                        x["host"] = f"{tag}{x['host']}"
                    x["subtag"] = tag
                    if "extra" not in x:
                        x["extra"] = []
                    for k in v:
                        x["extra"].append(k)
                    subtag_selection.append(subtag)
                    self.cases[subtag] = x
            selection = subtag_selection

        return selection

    def list(self):
        """List configurations."""
        logger.info("Available cases:")
        for x in self.cases:
            logger.info("    {}", x)
        logger.info("Selected cases:")
        case_print = self.cases if len(self.selection) == 0 else self.selection
        for x in case_print:
            logger.info("    {}", x)
            if self.verbose:
                logger.info("      {}", self.cases[x])

    def get_tactus_version(self):
        """Get tactus version info."""
        with open("pyproject.toml", "rb") as f:
            pyproject = tomli.load(f)
            deode_git = pyproject["tool"]["poetry"]["dependencies"]["deode"]
        if "tag" in deode_git:
            tag = deode_git["tag"]
        elif "branch" in deode_git:
            tag = deode_git["branch"]
        else:
            tag = "Unknown"

        tag = tag.replace("/", "_").replace(".", "_") + "_"
        return tag

    def expand_tests(self, defs):
        """Expand test arguments.

        Arguments:
           defs: (dict): Test definitions

        """
        prefix_map = {
            "intel": {"sp": "-sp", "dp": ""},
            "gnu": {"sp": "-sp-gnu", "dp": "-gnu"},
        }
        ial_hash = defs["ial"].get("ial_hash", "latest")
        prefix = f"{ial_hash[0:7]}_"
        self.tag = prefix
        self.bindir = defs["ial"]["bindir"].replace("@USER@", os.environ["USER"])

        self.selection = []
        for compiler, settings in defs["ial"]["tests"].items():
            for precision, confs in settings.items():
                dp_prefix = prefix_map[compiler]["dp"]
                sp_prefix = prefix_map[compiler]["sp"] if precision == "sp" else dp_prefix
                dp_path = f"{self.bindir}".replace("@CPTAG@", dp_prefix)
                sp_path = f"{self.bindir}".replace("@CPTAG@", sp_prefix)

                for conf in confs:
                    tag = f"{conf}_{compiler}_{precision}"
                    self.selection.append(tag)
                    self.cases[tag] = {
                        "base": conf,
                        "modifs": {
                            "scheduler": {"ecfvars": {"case_prefix": f"{prefix}{tag}_"}},
                            "submission": {
                                "bindir": dp_path,
                                "task_exceptions": {
                                    "Forecast": {
                                        "bindir": sp_path,
                                    }
                                },
                            },
                        },
                    }

    def prepare(self):
        """Prepare the host cases.

        Raises:
            KeyError: If case is not found

        Returns:
            host_cases: List of host cases
        """
        try:
            host_cases = [
                self.cases[case]["host"]
                for case in self.selection
                if "host" in self.cases[case]
            ]
        except KeyError as err:
            raise KeyError(
                f"The case is not an available\n"
                f" Avaiable cases are {list(self.cases)}"
            ) from err

        return host_cases

    def create(self, host_cases=None):
        """Create the tests.

        Arguments:
            host_cases (list, optional): List of host cases

        """
        os.makedirs(self.test_dir, exist_ok=True)
        if host_cases is None:
            cases = self.selection
            label = ""
        else:
            label = "host "
            cases = host_cases

        logger.info("Create {}config files in {}", label, self.test_dir)

        self.cmds = {}
        assigned = {}
        for i, (case, item) in enumerate(self.cases.items()):
            assigned[case] = i + 1

            if case not in cases:
                continue

            counter = assigned[item["host"]] if "host" in item else assigned[case]
            base = item["base"] if "base" in item else case
            subtag = item["subtag"] if "subtag" in item else ""
            host_case = item["hostname"] if "hostname" in item else ""
            host_domain = item["hostdomain"] if "hostdomain" in item else ""

            extra = list(self.extra) + (item["extra"] if "extra" in item else [])

            # Merge and replace macros
            modifs = merge_dicts(self.modifs, self.cases[case].get("modifs", {}), True)
            config = self.config.copy(
                update={
                    "modifs": modifs,
                    "modif_macros": {
                        "counter": counter,
                        "host_case": host_case,
                        "host_domain": host_domain,
                        "tag": self.tag,
                        "subtag": subtag,
                    },
                }
            )
            with contextlib.suppress(KeyError):
                config = config.expand_macros(True)

            # Build the command
            self.cmds[case] = self.get_cmd(
                case,
                config["modifs"],
                base,
                extra,
            )

    def get_cmd(
        self,
        case,
        modifs,
        base,
        extra,
    ):
        """Construct the final command.

        Arguments:
           case (str): Case to construct
           modifs (ParsedConfig object) : Config modifications
           base (str): Base configuration
           extra (list): Additional configration files to include

        Returns:
           cmd (list): List of commands

        """
        outfile = f"{self.test_dir}/modifs_{case}.toml"
        logger.info(" create: {}", outfile)
        modifs.save_as(outfile)

        cmd = [
            "case",
            f"?{GeneralConstants.PACKAGE_DIRECTORY}/data/config_files/configurations/{base}",
            extra,
            outfile,
            "-o",
            self.test_dir,
        ]

        return flatten_list(cmd)

    def configure(self, cmds=None):
        """Configure tests.

        Arguments:
            cmds (list, optional): List of commands (str)

        Returns:
            cases (dict): Dict of cases to run
        """
        if cmds is None:
            cmds = []
        cases = {}
        for case, cmd in self.cmds.items():
            logger.info("Configure case {} with\n", case)
            for c in cmds:
                cmd.append(c)
            cmd_txt = " ".join(cmd)
            logger.info("Use cmd:\n\n{}\n\n", cmd_txt)

            # Call tactus main to create new config, and possibly start suite
            tactus_main(cmd)

            # Update the case settings
            directory = Path(self.test_dir)
            config_file = max(directory.glob("*.toml"), key=lambda f: f.stat().st_mtime)
            with open(config_file, "rb") as f:
                definitions = tomli.load(f)
            cases[case] = {
                "config_name": os.path.basename(config_file.stem),
                "domain_name": definitions["domain"]["name"],
            }

        return cases

    def get_binaries(self):
        """Get the correct binaries."""
        basedir = os.getcwd()
        ial_hash = self.ial["ial_hash"]
        build_tar_path = self.ial["build_tar_path"]
        _bindir = self.ial["bindir"].replace("@USER@", os.environ["USER"])

        files = glob.glob(f"{build_tar_path}/*{ial_hash}*.tar")
        for f in files:
            ff = os.path.basename(f).replace(".tar", "")
            compiler = "intel"
            precision = "R64"
            if "-sp-" in ff:
                precision = "R32"
            if "-gnu-" in ff:
                compiler = "gnu"
            cptag = ff.replace(ial_hash, "").replace("ial", "")
            bindir = (
                _bindir.replace("@CPTAG@", cptag)
                .replace("@IAL_HASH@", ial_hash)
                .replace("@COMPILER@", compiler)
                .replace("@PRECISION@", precision)
                .replace("/bin", "")
            )
            os.makedirs(bindir, exist_ok=True)
            os.chdir(bindir)
            logger.info("Untar {} into {}", f, bindir)
            if not self.dry:
                os.system(f"tar xf {f}")  # noqa S605

        os.chdir(basedir)
        logger.info("All binaries copied. Rerun without '-p' to launch tests")


def execute(t, args):
    """Execute the stuff.

    Arguments:
        t (TestCases object): Object with test cases to execute
        args (ArgsPares object): Command line arguments

    """
    # Check dependencies and create possible host cases
    host_cases = t.prepare()
    t.create(host_cases)
    hostnames = t.configure()
    for case, item in t.cases.items():
        if "host" in item and item["host"] in hostnames:
            t.cases[case]["hostname"] = hostnames[item["host"]]["config_name"]
            t.cases[case]["hostdomain"] = hostnames[item["host"]]["domain_name"]

    # Create and run
    t.create()

    # Run
    if args.run:
        t.configure(([] if t.dry else ["--start-suite"]))


def main():
    """Main routine for the test runner."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        default=False,
        help="List selected cases",
        required=False,
    )
    parser.add_argument(
        "--dry",
        "-d",
        action="store_true",
        default=False,
        help="List selected cases",
        required=False,
    )
    parser.add_argument(
        "--config-file",
        "-c",
        dest="config_file",
        help="Used config file",
        required=False,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Increase verbosity",
        required=False,
    )
    parser.add_argument(
        "--prepare-binaries",
        "-p",
        action="store_true",
        default=False,
        help="Preare binaries from an IAL hash",
        required=False,
    )

    parser.add_argument(
        "-m",
        action="store_false",
        dest="run",
        default=True,
        help="Only run the modify generation setp",
        required=False,
    )

    args = parser.parse_args()

    t = TestCases(args=args)

    if args.prepare_binaries:
        t.get_binaries()
    elif args.list:
        t.list()
    elif args.config_file is not None:
        execute(t, args)


if __name__ == "__main__":
    logger.enable(GeneralConstants.PACKAGE_NAME)
    main()
