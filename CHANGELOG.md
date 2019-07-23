# Changelog

## Unreleased

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

