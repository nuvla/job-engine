# Changelog

## Unreleased

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
  - Update start deployment options to support restart policy conditions, 
    cpu, ram
  - Deployment code reorganization
  - Release script fix
  - move reusable parts in util directory for actions 
  - connector docker, stop container, if service not found should not return an error 
  - deployment enhance exception management and always leave deployment in a final state
  - deployment start, stop, deployment resource changed

## [0.0.3] - 2019-04-18

### Changed

  - first release of job container

