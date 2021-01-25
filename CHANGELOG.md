# Changelog

## Unreleased

### Added

 - New distributor for setting nuvlabox status to offline
 - New Job Engine Lite Docker image build, optimized for running jobs from within an infrastructure, with multi-arch support
 
## [2.10.0] - 2020-12-10

### Added

 - Actions for NuvlaBox update

## [2.9.0] - 2020-12-07

### Added

  - BUILD - Support github actions

## [2.8.1] - 2020-12-04

### Added

 - Support for API Key login to Nuvla

### Changed

 - Action deployment_update for all 4 supported COE

## [2.8.0] - 2020-11-16

### Added

 - Action and distributor for updating vulnerabilities database

## [2.7.1] - 2020-10-12

### Changed

 - Distributor usage report - Fix bug in jobs generation

## [2.7.0] - 2020-10-09

### Added

 - Action dct_check - Check if docker images are trusted

### Changed

  - Dependencies - Bump stripe to v2.54.0
  - Action usage report - Remove VPN from usage reporting
  - Action usage report - Report usage of nonfree deployments
  - Distributor usage report - Create jobs for nonfree deployments

## [2.6.0] - 2020-09-04

### Changed

 - Action usage_report: bugfix on exclusion of deployments
   running on NuvlaBoxes
 - COE - add stop and start actions

## [2.5.4] - 2020-08-28

### Changed

 - Action usage_report: count only online NuvlaBoxes

## [2.5.3] - 2020-08-03

### Changed

 - Docker host format is now different from docker-compose

## [2.5.2] - 2020-08-03

### Changed

 - Docker-compose --host format changed from v1.26.0

## [2.5.1] - 2020-08-03

### Changed

  - Copy docker-compose binary from official repository
  - Fix bug in docker-compose missing a module

## [2.5.0] - 2020-07-31

### Added

  - New action to restart NuvlaBox data gateway streaming

### Changed

  - Copy docker-compose binary to avoid having building tools in the image
  - Usage report distributor - Do not yield jobs if no customers
  - Docker machine connector - new script to install Rancher
  - Deployment state job was split into two for "new" and "old" deployments with
    configurable check intervals. This was done to reduce unnecessary load on
    the server and remote COEs.
  - Jobs cleanup executor now goes via server API instead of directly to ES.

## [2.4.0] - 2020-07-06

### Added

 - Added new actions for adding and revoking SSH keys from
   the NuvlaBox
 - Deployment State job in push mode, as an entrypoint
 - New job distributor and executor action for usage report
 - New executor that provisions Docker Swarm and Kubernetes
   on AWS, Azure, Google Cloud, and Exoscale.

### Changed

 - Dependency nuvla-api updated to v3.0.2
 - Added cross-platform compatibility for Docker image 
 - Fixed Docker Compose deployment bug - allow containers to
   have internal ports that are not published to the host

## [2.3.16] - 2020-05-11

### Changed

  - Deployment start - add NUVLA_DEPLOYEMT_UUID env var

## [2.3.15] - 2020-04-14

### Changed

  - Docker cli connector - export node ip and ports when a service
    use host mode ports

## [2.3.14] - 2020-03-27

### Added

  - validate-docker-compose - new action
  - docker_compose_cli_connector - new connector for docker-compose
  - enable-stream and disable-stream - new nuvlabox actions

### Changed

  - reuse python library wrappers
  - deployment_* actions to support docker-compose apps

## [2.3.13] - 2020-03-06

### Added

  - update_nuvlabox_releases - new action
  - job_distributor_nuvlabox_releases - new distributor 

### Changed

  - Deployment start, update - support private registries
  - Connectors - docker api, docker cli and kubernetes cli support 
    private registries
  - Found bug in `lstrip` method
  - make action `credential_check` also check for swarm mode and status
  - reduced number of api calls in connector_factory

## [2.3.12] - 2020-01-23

### Changed

  - Deployment log - docker log command deadlock fixed by command timeout
  - Timeout run command to 120s by default and 5s to credential check 
  - Credential check - implement check credential action

## [2.3.11] - 2020-01-10

### Changed

  - Kubernetes connector - deployment start support env vars substitution

## [2.3.10] - 2019-12-09

### Changed

  - Kubernetes connector - support deployment logs action
  - Fix regression stop docker application

## [2.3.9] - 2019-12-09

### Changed

  - Kubernetes - deployment support start, stop, state actions
  - Install kubectl command
  - Update docker client to 19.03.5

## [2.3.8] - 2019-11-13

### Changed

 - Nuvlabox decommission - Delete vpn credential
 - Job restoration - Fix limit restore to 10000

## [2.3.7] - 2019-10-10

### Changed

 - Update requirements to nuvla-api 2.1.1

## [2.3.6] - 2019-09-18

### Changed

  - Action service image state - consider nuvla as source of truth for deployed image version
  - Action service and component image state - module path appended to the notification message

## [2.3.5] - 2019-09-04

### Added

  - Service image state distributor and action added
  - Component image state distributor and action added
  - Deployment log fetch action added

### Changed

  - Deployment action - Log message change
  - Deployment state - Deployment state should not be set to state ERROR when this action fail
  - Logging - remove thread name from logging since it's no more multi-threaded
  - Successfully executed actions are in failed state because do_work 
    isn't returning result code. This was the case for jobs_cleanup, nuvlabox_decommission, 
    infrastructure_*
  - Docker cli connector - when cacert is required connection fail fix
  - Fix calculation of replicas.running to properly take into account
    the running task state
  - Add deployment parameters to provide information about current
    Docker task: current.desired.state, current.state, and current.error. 
  - Fix misspelled method name in NuvlaBox decommissioning job that
    blocked deletion of NuvlaBox resources. 

## [2.3.4] - 2019-08-07

### Changed

  - Properly stop fix for job executor and and job distributor
  - Nuvlabox decommission - Delete linked nuvlabox-peripheral
  - Start deployment - When no volume options is set in deployment mounts, 
    start deployment job is failing

## [2.3.3] - 2019-07-29

### Changed

  - Connector Docker Cli - Fix when no ports are defined, the deploymnet fail

## [2.3.2] - 2019-07-25

### Changed

  - Deployment actions - Put deployment in final state before raising the exception

## [2.3.1] - 2019-07-24

### Changed

  - Fix in Deployment start component regression
  - Deployment action do not cat exception to force full stack trace

## [2.3.0] - 2019-07-24

### Added

  - Added support for start stop state deployment of subtype application
  - Docker cli connector

### Changed

  - When an error occur during execution of a job, the final state is 
    set to 'FAILED'

## [2.2.0] - 2019-06-20

### Added

  - add script to restore zookeeper jobs from elasticsearch

### Changed

  - Deployment - credential-id renamed parent
  - Deployment parameter - field deployment/href renamed parent
  - Executor is now mono-threaded. Use multiple executors to run 
    multiple jobs in parallel.

## [2.1.0] - 2019-06-07

### Added

  - Allow authentication with server via request headers
  - Nuvlabox delete job
  - Deployment state job

### Changed

  - Reduce the sleep time to 30 seconds after an error when contacting
    the Nuvla server
  - Deployment stop - delete credential on stop
  - Update start deployment options to support restart policy 
    conditions, cpu, ram
  - Deployment code reorganization
  - Release script fix
  - Move reusable parts in util directory for actions 
  - Connector docker, stop container, if service not found should not 
    return an error 
  - Deployment enhance exception management and always leave deployment 
    in a final state
  - Deployment start, stop, deployment resource changed

## [0.0.3] - 2019-04-18

### Changed

  - first release of job container

