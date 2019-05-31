# Changelog

## [Unreleased]

### Added

  - Nuvlabox delete job (wip)
  - Deployment state job

### Changed

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

 
