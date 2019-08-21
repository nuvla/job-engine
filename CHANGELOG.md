# Changelog

## Unreleased

### Added

  - Service image state distributor and action added
  - Component image state distributor and action added
  - Deployment log fetch action added

### Changed

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

