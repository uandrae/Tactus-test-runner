# Tactus-test-runner

The Tactus-test-runner runs a number of configurations as defined in the used config file. 

We currently have the following config files under the directory config_files

 - atos_bologna.toml : Complete set of tests for atos_bologna
 - lumi.toml : Complete set of tests for lumi
 - ial_pr_atos_bologna.toml : Test ia IAL pr on the toy domain
 - ial_pr_atos_large_bologna.toml : Test ia IAL pr on the standard domain

## Prepare

Define the correct tactus version to use in pyproject.toml. This may be a tag or a branch.

```
[tool.poetry.dependencies]
  deode = {git = "git@github.com:uandrae/Deode-Prototype.git", branch = "release/v0.23.0"}
  #deode = {git = "git@github.com:destination-earth-digital-twins/Deode-Workflow.git", tag = "v0.22.0"}
```

Optionally define the location of your virtual environment in poetry.toml

```
[virtualenvs]
  in-project = false
  path = "some_useful_path"
```

## Install

Install the package and all tactus dependencies with poetry. Potentially locate the 

```
poetry install
```

```
poetry shell
```

## Check

```
ttr -c config_files/CURRENT_HOST.toml -l
```

where CURRENT_HOST is one of atos_bologna or lumi

## Run
```
ttr -c config_files/CURRENT_HOST.toml
```

This will create a directory according to the tag and create all config files in this directory. For each config a tactus ecflow run will be launched. To only prepare config files without running tactus do:

```
ttr -c config_files/CURRENT_HOST.toml -d 
```

## Noteable 

There are a few `target` configurations that will require the host run to complete before it works. These runs will fail and can be requed once the host run has completed.

## About the config file

The config file has a for main sections: general, case, modifs and ial. Here we explain the usage of each

### General

The general section defines the selection of cases and possible compiler extensions. If tag is not set it's taken from the used tactus branch or tag. In extra we can define extra config files to include.

```
[general]
  selection = [
    "cy49t2_alaro",
    "cy49t2_alaro_target",
  ]
  # tag = "v0_23_0_"
  # Uncomment this for intel and gnu runs
  subtags = [
    {intel_ = []},
    {gnu_ = ["deode/data/config_files/modifications/submission/atos_bologna_gnu.toml"]},
  ]
  extra = []

```

### Case

Here we define the config settings per case.

- base gives the config to start from
- host defines the forcing run for a target run
- extra is extra config files to add for this specific case
- case.X.modifs.Y allows to modify abitrary config settings for this case only

```
[cases.cy49t2_alaro_eps]
  host = "alaro"
  base = "cy49t2_alaro"
  extra = [
    "deode/data/config_files/include/eps/eps_7members.toml",
    "deode/data/config_files/include/eps/alaro.toml",
  ]

[cases.cy49t2_alaro_eps.modifs.eps.general]
  members = "0:3"
```

### Modifs

Here we define global modifications to the default config files. Works the same way as for the config modifications mentioned above.

```
[modifs.archiving.FDB.fdb.fpgrib_files]
  active = false
```

### IAL

This section is for IAL PR testing. Here we define

- active: Switch on or off
- ial_hash: Full hash of the tarball containing the compiled code produced by the github actions. Find if from the github actions, https://github.com/destination-earth-digital-twins/IAL/actions
- build_tar_path: Path to the tarball
- bindir: The target bindir to use

In `ial.test.compiler_name` we define which tests to do in single and double precision respectively for each available compiler. We have

```
[ial]
  active = true
  ial_hash = "be0fe3c3429fcbdf4515f5b58a5cf30689cf66f8"
  bindir = "/scratch/@USER@/ial_binaries/@IAL_HASH@/@COMPILER@/@PRECISION@/bin"
  build_tar_path = "/scratch/deployde330"

[ial.tests.intel]
  R32 = ["cy49t2_arome","cy49t2_harmonie_arome"]
  R64 = ["cy49t2_alaro","cy49t2_arome","cy49t2_harmonie_arome"]
[ial.tests.gnu]
  R32 = ["cy49t2_arome","cy49t2_harmonie_arome"]
  R64 = ["cy49t2_alaro","cy49t2_arome","cy49t2_harmonie_arome"]
```

We can check what configurations to expect by
```
$ poetry run ttr -c config_files/ial_pr_atos_bologna.toml -l
2025-12-05 09:06:45 | INFO     | Using config file: config_files/ial_pr_atos_bologna.toml
2025-12-05 09:06:45 | INFO     |  tag: 2951f1a_
2025-12-05 09:06:45 | INFO     | Available cases:
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R32
2025-12-05 09:06:45 | INFO     | Selected cases:
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_gnu_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_alaro_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R64
2025-12-05 09:06:45 | INFO     |     cy49t2_arome_intel_R32
2025-12-05 09:06:45 | INFO     |     cy49t2_harmonie_arome_intel_R32
```
First we need to fetch the binaries
```
$ poetry run ttr -c config_files/ial_pr_atos_bologna.toml -p
2025-12-05 09:09:59 | INFO     | Using config file: config_files/ial_pr_atos_bologna.toml
2025-12-05 09:09:59 | INFO     |  tag: 2951f1a\_
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-sp-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/intel/R32
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-gnu-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/gnu/R64
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-sp-gnu-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/gnu/R32
2025-12-05 09:09:59 | INFO     | Untar /scratch/deployde330/ial-2951f1a1dc2df82471e857a3331df8bb35050745.tar into /scratch/snh/ial_binaries/2951f1a1dc2df82471e857a3331df8bb35050745/intel/R64
2025-12-05 09:09:59 | INFO     | All binaries copied. Rerun without '-p' to launch tests
```
Finally we can launch the runs by
```
$ poetry run ttr -c config_files/ial_pr_atos_bologna.toml 
```
Note the corresponding config file `config_files/ial_pr_large_atos_bologna.toml` for large domain tests.
