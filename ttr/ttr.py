import argparse
import contextlib
import copy
import glob
import os
import subprocess

import tomli
import tomlkit
from deode.config_parser import GeneralConstants
from deode.general_utils import merge_dicts


class TestCases:
    def __init__(self, args):
        # with open(config_file, "r", encoding="utf-8") as f:
        # definitions = json.load(f)
        with open(args.config_file, "rb") as f:
            definitions = tomli.load(f)

        self.verbose = args.verbose
        self.definitions = definitions
        # Definitions
        self.cases = definitions.get("cases", {})
        self.selection = definitions["general"].get("selection", [])
        self.extra = definitions["general"].get("extra", [])
        if len(self.selection) == 0:
            self.selection = list(self.cases)

        # Handle subtags and update selection accordingly
        subtags = definitions["general"].get("subtags", [])
        if len(subtags) > 0:
            subtag_selection = []
            for key in subtags:
                tag, v = key.popitem()
                for selection in self.selection:
                    subtag = f"{tag}{selection}"
                    x = copy.deepcopy(self.cases[selection])
                    if "base" not in x:
                        x["base"] = selection
                    if "host" in x:
                        x["host"] = f"{tag}{x['host']}"
                    x["subtag"] = tag
                    if "extra" not in x:
                        x["extra"] = []
                    for k in v:
                        x["extra"].append(k)
                    subtag_selection.append(subtag)
                    self.cases[subtag] = x
            self.selection = subtag_selection

        self.dry = args.dry if args.dry else definitions["general"].get("dry", True)
        self.tag = definitions["general"].get("tag", "")
        self.modifs = definitions["modifs"]

        with contextlib.suppress(KeyError):
            if definitions["ial"].get("active", False):
                self.expand_tests(definitions)

        self.test_dir = definitions.get("test_dir", f"{self.tag}configs")

        print("Using config file:", args.config_file)
        print("         test tag:", self.tag)
        # Actions
        if args.list:
            print("\nAvailable cases:")
            for x in self.cases:
                print(f'    "{x}",')
            print("\nSelected cases:")
            case_print = self.cases if len(self.selection) == 0 else self.selection
            for x in case_print:
                print(f'    "{x}",')
                if self.verbose:
                    print(f'      "{self.cases[x]}",')

    def expand_tests(self, defs):
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
                dp_path = f"{self.bindir}".replace("@CPTAG@", dp_prefix).replace(
                    "@IAL_HASH@", ial_hash
                )
                sp_path = f"{self.bindir}".replace("@CPTAG@", sp_prefix).replace(
                    "@IAL_HASH@", ial_hash
                )

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
        host_cases = []
        for case in self.selection:
            try:
                if "host" in self.cases[case]:
                    host_cases.append(self.cases[case]["host"])
            except KeyError:
                raise ValueError(
                    f"{case} is not an available case\n Avaiable cases are {list(self.cases)}"
                )
        return host_cases

    def create(self, host_cases=None):
        os.makedirs(self.test_dir, exist_ok=True)
        print(f"Create config files in {self.test_dir}")

        self.cmds = {}
        if host_cases is None:
            cases = self.selection
        else:
            cases = host_cases
        assigned = {}
        print("cases:", cases)
        for i, (case, item) in enumerate(self.cases.items()):
            assigned[case] = i + 1

            if case not in cases:
                continue

            host = ""
            if "host" in item:
                j = assigned[item["host"]]
                host = item["host"]
            elif "start" in item:
                j = item["start"]
            else:
                j = assigned[case]

            base = item["base"] if "base" in item else case
            subtag = item["subtag"] if "subtag" in item else ""
            extra = [x for x in self.extra]
            _extra = item["extra"] if "extra" in item else []
            for e in _extra:
                extra.append(e)
            suffix = item["suffix"] if "suffix" in item else ""
            hostname = item["hostname"] if "hostname" in item else ""
            hostdomain = item["hostdomain"] if "hostdomain" in item else ""
            cmd = self.get_cmd(
                j,
                case,
                self.tag,
                subtag,
                base,
                extra=extra,
                host=host,
                suffix=suffix,
                hostname=hostname,
                hostdomain=hostdomain,
            )
            self.cmds[case] = cmd

    def get_cmd(
        self,
        i,
        case,
        tag="",
        subtag="",
        base=None,
        extra=[],
        host="",
        suffix="",
        hostname="",
        hostdomain="",
    ):
        if base is None:
            base = case

        cmd = [
            "deode",
            "case",
            f"?{GeneralConstants.PACKAGE_DIRECTORY}/data/config_files/configurations/{base}",
        ]

        for x in extra:
            cmd.append(x)

        tail = [
            self.modif(
                i,
                case,
                host=f"{tag}{subtag}{host}",
                hostname=hostname,
                hostdomain=hostdomain,
                subtag=subtag,
            ),
            "-o",
            self.test_dir,
        ]
        for x in tail:
            cmd.append(x)

        return cmd

    def modif(
        self, i, case, outfile=None, host="", hostname="", hostdomain="", subtag=""
    ):
        if outfile is None:
            outfile = f"{self.test_dir}/modifs_{case}.toml"

        print(" create:", outfile)
        modifs = merge_dicts(self.modifs, self.cases[case].get("modifs", {}), True)
        try:
            x = tomlkit.dumps(modifs).format(
                i=i, tag=self.tag, hostname=hostname, hostdomain=hostdomain, subtag=subtag
            )
            x = tomlkit.parse(x)
        except KeyError:
            raise KeyError("Missing substition in modif section")

        with open(outfile, mode="w", encoding="utf8") as fh:
            tomlkit.dump(x, fh)

        return outfile

    def configure(self, cmds=[]):
        cases = {}
        for case, cmd in self.cmds.items():
            print("Configure case", case, "with\n")
            for c in cmds:
                cmd.append(c)
            print(" ".join(cmd))
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
            except (subprocess.CalledProcessError, KeyError) as e:
                print(result.stderr)
                print(result)
                print("Command failed!")
                print(f"Return code: {result.returncode}")
                print(f"Command: {result.cmd}")
                print(f"stdout: {result.stdout}")
                print(f"stderr: {result.stderr}")
                raise RuntimeError from e

            print(result.stderr)
            lines = result.stderr.split("INFO")
            for line in lines:
                if "Save config" in line:
                    config_name = (
                        line.split("\n")[0].split(" ")[-1].split("/")[-1].split(".")[0]
                    )
                    print("config_name:", config_name)
                    config_file = f"{self.test_dir}/{config_name}.toml"
                    with open(config_file, "rb") as f:
                        definitions = tomli.load(f)
                    cases[case] = {
                        "config_name": config_name,
                        "domain_name": definitions["domain"]["name"],
                    }

        return cases

    def get_binaries(self):
        basedir = os.getcwd()
        ial_hash = self.definitions["ial"]["ial_hash"]
        build_tar_path = self.definitions["ial"]["build_tar_path"]
        files = glob.glob(f"{build_tar_path}/*{ial_hash}*.tar")
        for f in files:
            ff = os.path.basename(f).replace(".tar", "")
            cptag = ff.replace(ial_hash, "").replace("ial", "")
            bindir = (
                self.bindir.replace("@CPTAG@", cptag)
                .replace("-@IAL_HASH@", ial_hash)
                .replace("/bin", "")
            )
            os.makedirs(bindir, exist_ok=True)
            os.chdir(bindir)
            print(f"Untar {f} into {bindir}")
            os.system(f"tar xf {f}")

        os.chdir(basedir)
        print("All binaries copied. Rerun without '-p' to launch tests")


def execute(t):
    # Check dependencies
    host_cases = t.prepare()
    t.create(host_cases)
    hostnames = t.configure()
    for case, item in t.cases.items():
        if "host" in item:
            if item["host"] in hostnames:
                print(item["host"], hostnames[item["host"]])
                t.cases[case]["hostname"] = hostnames[item["host"]]["config_name"]
                t.cases[case]["hostdomain"] = hostnames[item["host"]]["domain_name"]

    # Create and run
    t.create()

    cmd = []
    if not t.dry:
        cmd.append("--start-suite")
    t.configure(cmd)


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
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
        default="test_cases.toml",
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
        help="Preare binaries from a IAL hash",
        required=False,
    )

    args = parser.parse_args()

    t = TestCases(args=args)

    if args.prepare_binaries:
        t.get_binaries()
    else:
        if not args.list:
            execute(t)


if __name__ == "__main__":
    main()
