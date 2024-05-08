# Nuvla Job Engine

[![UnitTests and Build Docker Dev. Image](https://github.com/nuvla/job-engine/actions/workflows/devel.yml/badge.svg)](https://github.com/nuvla/job-engine/actions/workflows/devel.yml)

This repository contains the code and configuration for the Job engine, 
packaged as a Docker container. 

Nuvla job engine use cimi job resource and zookeeper as a locking queue. 
It's done in a way to be horizontally scalled on different nodes.

## Artifacts

 - `nuvla/job:<version>`. A Docker container that can be obtained from
   the [nuvla/job repository](https://hub.docker.com/r/nuvla/job)
   in Docker Hub. The tags indicate the release number.

## Contributing

### Source Code Changes

To contribute code to this repository, please follow these steps:

 1. Create a branch from main with a descriptive, kebab-cased name
    to hold all your changes.

 2. Follow the developer guidelines concerning formatting, etc. when
    modifying the code.
   
 3. Once the changes are ready to be reviewed, create a GitHub pull
    request.  With the pull request, provide a description of the
    changes and links to any relevant issues (in this repository or
    others). 
   
 4. Ensure that the triggered CI checks all pass.  These are triggered
    automatically with the results shown directly in the pull request.

 5. Once the checks pass, assign the pull request to the repository
    coordinator (who may then assign it to someone else).

 6. Interact with the reviewer to address any comments.

When the reviewer is happy with the pull request, he/she will "squash
& merge" the pull request and delete the corresponding branch.


### Code Formatting

The bulk of the code in this repository is written in Python.

The formatting follows the coding style in defined in PEP 8.


### Job engine behavior

 - Each action should be distributed by a standalone distributor
 - More than one distributor for the same action can be started but only
   one will be elected to distribute the job
 - Executor load actions dynamically at startup time
 - Zookeeper is used as a Locking queue containing only job uuid in 
   /job/entries
 - Running jobs are put in zookeeper under /job/taken
 - If executor is unable to communicate with CIMI, the job in running 
   state is released (put back in zookeeper queue).
 - The action implementation should take care to continue or to make the 
   cleanup of a running interrupted job
 - If the connection break with zookeeper, job in exection will be 
   released automatically. This is because /job/taken entries 
   are ephemeral nodes.
 - Stopping the executor will try to make a proper shuttdown by waiting 
   2 minutes before killing the process. Each thread that terminate his 
   running action will not take a new one.

## Running unit tests
Before running unit tests with `tox` you need to generate requirements file out. To do so, we first need to
generate the test requirements file. This is done using poetry requirements exporter which can be installed as follows:

```shell
pip install poetry poetry-plugin-export
```

Then run export command:

```shell
poetry export -f requirements.txt -o requirements.test.txt --without-hashes --without-urls --with test --with server
```

Then run the unit tests with:

```shell
tox
```

## Locally Building Job Engine
Before running `docker build` you need to generate requirements file and the wheel package.
To do, install poetry and poetry-plugin-export as described above and then run:

```shell
poetry build --format=wheel
poetry export -f requirements.txt -o dist/requirements.txt --without-hashes --without-urls --with server
```
The order of the commands might be important since the requirements file output goes into dist/ directory which is created by the first command.



Then building the image requires the following command:
```shell
export JOB_ENGINE_VERSION=$(poetry version -s)
docker build --build-arg="PACKAGE_TAG=${JOB_ENGINE_VERSION}" -t local/job:${JOB_ENGINE_VERSION} .
```


## Copyright

Copyright &copy; 2019-2024, SixSq SA

## License

Licensed under the Apache License, Version 2.0 (the "License"); you
may not use this file except in compliance with the License.  You may
obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied.  See the License for the specific language governing
permissions and limitations under the License.
