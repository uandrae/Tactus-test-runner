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

Define the location of your virtual environment in poetry.toml

```
[virtualenvs]
  path = "some_useful_path"
```

## Install

Install the package and all tactus dependencies with poetry. Potentially locate the 

```
poetry install

## Check

```
ttr -c CURRENT_HOST.toml -l
```

where CURRENT_HOST is one of atos_bologna or lumi

## Run
```
ttr -c CURRENT_HOST.toml
```

This will create a directory according to the tag and create all config files in this directory. For each config a tactus run will be launched. To only prepare config files without running tactus do.

```
ttr -c CURRENT_HOST.toml -d 
```

## Noteable 

There are a few `target` configurations that will require the host run to complete before it works. These runs will fail and can be requed once the host run has completed.
