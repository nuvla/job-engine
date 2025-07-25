# Changelog

## Released

## [5.1.3](https://github.com/nuvla/job-engine/compare/5.1.2...5.1.3) (2025-07-15)


### Bug Fixes

* **helm:** support user defined namespace with nuvlaNamespaceOverride value ([#450](https://github.com/nuvla/job-engine/issues/450)) ([f2fd6df](https://github.com/nuvla/job-engine/commit/f2fd6dfb99c7c95c224938e8e0d0fe0f319077db))

## [5.1.2](https://github.com/nuvla/job-engine/compare/5.1.1...5.1.2) (2025-07-03)


### Bug Fixes

* **nuvlabox_offline.py:** Catch exception and add more info logging ([f61c5c6](https://github.com/nuvla/job-engine/commit/f61c5c60b031499a69eb26c99355e6b8a39ef9ea))

## [5.1.1](https://github.com/nuvla/job-engine/compare/5.1.0...5.1.1) (2025-06-17)


### Bug Fixes

* **distributor.py:** Recreate thread when exception is thrown in distribution ([#445](https://github.com/nuvla/job-engine/issues/445)) ([9b32214](https://github.com/nuvla/job-engine/commit/9b3221406b03733cf69af25d86d423241f384b51))
* Improve Helm and Kubernetes credentials usage on Clouds and NuvlaEdge ([#444](https://github.com/nuvla/job-engine/issues/444)) ([9c86db0](https://github.com/nuvla/job-engine/commit/9c86db02298f484a3031f4b3de83c79f114eb0e0))

## [5.1.0](https://github.com/nuvla/job-engine/compare/5.0.2...5.1.0) (2025-06-10)


### Features

* **coe_resources.py:** Support for docker pull image from private registries ([#441](https://github.com/nuvla/job-engine/issues/441)) ([b0eca48](https://github.com/nuvla/job-engine/commit/b0eca48fae6b8fc96416be6dfd46d3c46510ae90))


### Bug Fixes

* **Dockerfile:** Install stable Kubectl CLI from dl.k8s.io instead of apk package ([b0eca48](https://github.com/nuvla/job-engine/commit/b0eca48fae6b8fc96416be6dfd46d3c46510ae90))

## [5.0.2](https://github.com/nuvla/job-engine/compare/5.0.1...5.0.2) (2025-04-17)


### Bug Fixes

* **executor.py:** UnfinishedBulkActionToMonitor should finish execution without setting job to FAILED ([06d4a0b](https://github.com/nuvla/job-engine/commit/06d4a0bf96e8b73f5e96ace15de63b2fa39983d1))

## [5.0.1](https://github.com/nuvla/job-engine/compare/5.0.0...5.0.1) (2025-04-17)


### Bug Fixes

* **executor.py:** Avoid log error on LocalOneJobQueue consume and release ([64b84c7](https://github.com/nuvla/job-engine/commit/64b84c7d0114cf5b23abb8553dfd2ef4b1c9066b))
* **job.py:** Version is now a simple number ([64b84c7](https://github.com/nuvla/job-engine/commit/64b84c7d0114cf5b23abb8553dfd2ef4b1c9066b))

## [5.0.0](https://github.com/nuvla/job-engine/compare/4.10.1...5.0.0) (2025-04-16)


### ⚠ BREAKING CHANGES

* Signatures of Executor's methods and Job have changed

### Bug Fixes

* don't create namespace if already defined in user manifests ([#432](https://github.com/nuvla/job-engine/issues/432)) ([36e7afa](https://github.com/nuvla/job-engine/commit/36e7afad4a4769e5e18b44519c45acb51af2f41f))


### Code Refactoring

* Refactor executor, job and add tests ([#435](https://github.com/nuvla/job-engine/issues/435)) ([d406034](https://github.com/nuvla/job-engine/commit/d406034af26f43598fc734104b9f2d844d87e28a))
* Signatures of Executor's methods and Job have changed ([d406034](https://github.com/nuvla/job-engine/commit/d406034af26f43598fc734104b9f2d844d87e28a))

## [4.10.1](https://github.com/nuvla/job-engine/compare/4.10.0...4.10.1) (2025-04-04)


### Bug Fixes

* **distribution.py:** Avoid stopping distribution on first exception ([#433](https://github.com/nuvla/job-engine/issues/433)) ([45f083c](https://github.com/nuvla/job-engine/commit/45f083c9c9ac8683de16d9287a2a071ef715ea1c))
* **distribution.py:** Sleep take into account execution time ([45f083c](https://github.com/nuvla/job-engine/commit/45f083c9c9ac8683de16d9287a2a071ef715ea1c))
* **k8s registries creds:** create registries creds for the whole namespace ([#430](https://github.com/nuvla/job-engine/issues/430)) ([111de81](https://github.com/nuvla/job-engine/commit/111de8131a47ddc9c032aa28c35329a44abe08dd))

## [4.10.0](https://github.com/nuvla/job-engine/compare/4.9.2...4.10.0) (2025-01-27)


### Features

* Added cleanup of volumes and images on deployment stop action ([#425](https://github.com/nuvla/job-engine/issues/425)) ([a5b7ff1](https://github.com/nuvla/job-engine/commit/a5b7ff1701dbab69f626010ad9e31b77a47c1e70))


### Bug Fixes

* **BulkDeploymentSetStop:** missing param to EdgeResolver in dg stop action ([#427](https://github.com/nuvla/job-engine/issues/427)) ([1d55c29](https://github.com/nuvla/job-engine/commit/1d55c290841fbbe798a0d31cff3789f0e9d1a4cf))
* **BulkDeploymentSetStop:** missing param to EdgeResolver in dg stop action ([#429](https://github.com/nuvla/job-engine/issues/429)) ([e08e762](https://github.com/nuvla/job-engine/commit/e08e762af6480b00b56c15afe14a4090f37db4ae))
* **CI:** Fixed poetry deprecated plugin. Manual installation required ([#426](https://github.com/nuvla/job-engine/issues/426)) ([a8fb4b0](https://github.com/nuvla/job-engine/commit/a8fb4b08fd8874417da3ce21990201c292ba8364))

## [4.9.2](https://github.com/nuvla/job-engine/compare/4.9.1...4.9.2) (2024-12-24)


### Bug Fixes

* **Dockerfile:** Upgrade kubectl from 1.31 to 1.32 ([#423](https://github.com/nuvla/job-engine/issues/423)) ([263ff27](https://github.com/nuvla/job-engine/commit/263ff2716b87c593faba9ab72226572403b608b0))

## [4.9.1](https://github.com/nuvla/job-engine/compare/4.9.0...4.9.1) (2024-12-19)


### Bug Fixes

* **Action service_image_state:** Removed, deprecated ([672c3f1](https://github.com/nuvla/job-engine/commit/672c3f11d30cb4cf61a27ae8bc8b70ee6d94a614))
* **Bulk job monitoring:** Refactor and change monitor data format to enhance UI/UX ([a131336](https://github.com/nuvla/job-engine/commit/a131336f99d6b8dabaa73018c729d69c05fc5ab7))
* **Bulk job monitoring:** Timeout reduced from 1 day to 1 hour ([a131336](https://github.com/nuvla/job-engine/commit/a131336f99d6b8dabaa73018c729d69c05fc5ab7))
* **Deployment Group:** Do not launch actions for offline edges ([#419](https://github.com/nuvla/job-engine/issues/419)) ([a131336](https://github.com/nuvla/job-engine/commit/a131336f99d6b8dabaa73018c729d69c05fc5ab7))
* **Distribution service_image_state:** Removed, deprecated ([672c3f1](https://github.com/nuvla/job-engine/commit/672c3f11d30cb4cf61a27ae8bc8b70ee6d94a614))
* **wrong_infra_selected:** filter infra services based on DG subtype ([#421](https://github.com/nuvla/job-engine/issues/421)) ([00d1c01](https://github.com/nuvla/job-engine/commit/00d1c01a530c7dff972f4572e54508f89f5d0672))

## [4.9.0](https://github.com/nuvla/job-engine/compare/4.8.3...4.9.0) (2024-12-09)


### Features

* **deployment_state:** only distribute deployment_state_60 to deployments not deployed on NuvlaEdge ([#416](https://github.com/nuvla/job-engine/issues/416)) ([5d81f94](https://github.com/nuvla/job-engine/commit/5d81f9454c2c2817855438bc4116c874fd17b812))


### Bug Fixes

* **dg-auto-update-acl:** make jobs created by auto update visible to the dg owner ([#417](https://github.com/nuvla/job-engine/issues/417)) ([dac2a9a](https://github.com/nuvla/job-engine/commit/dac2a9a1982e2ee42ec605e03bee2559a80006fb))

## [4.8.3](https://github.com/nuvla/job-engine/compare/4.8.2...4.8.3) (2024-11-26)


### Bug Fixes

* **bulk_deployment_set_apply.py:** Avoid creating deployment without target credential ([#414](https://github.com/nuvla/job-engine/issues/414)) ([858dae1](https://github.com/nuvla/job-engine/commit/858dae166c4e6a8248b33786a3dc6bd1f19aa69d))

## [4.8.2](https://github.com/nuvla/job-engine/compare/4.8.1...4.8.2) (2024-11-21)


### Bug Fixes

* **action_bulk_deployment_set_apply:** Take Operational Status files overrides into account when creating deployments of a DG ([e656cd9](https://github.com/nuvla/job-engine/commit/e656cd9af34c160dd86e900857bd23944e757a35))
* **dg-permission-issues:** make api calls with the right permissions ([#410](https://github.com/nuvla/job-engine/issues/410)) ([e656cd9](https://github.com/nuvla/job-engine/commit/e656cd9af34c160dd86e900857bd23944e757a35))

## [4.8.1](https://github.com/nuvla/job-engine/compare/4.8.0...4.8.1) (2024-11-20)


### Bug Fixes

* **Deployment group:** Deploy on docker by default if both docker and kubernetes are available (temporary fix) ([bbdfac2](https://github.com/nuvla/job-engine/commit/bbdfac23b8e5212372cc27a8c963524a32eae1b1))
* **update:** Added K8s nuvlaedge update operation parsing capabilities for helm params configuration ([#409](https://github.com/nuvla/job-engine/issues/409)) ([dedccc9](https://github.com/nuvla/job-engine/commit/dedccc9fe421c032bb71b1c4581c3b2dcfa77135))

## [4.8.0](https://github.com/nuvla/job-engine/compare/4.7.1...4.8.0) (2024-11-20)


### Features

* **deployment_set_automatic_update.pt:** New action support auto-update deployment group ([9839de3](https://github.com/nuvla/job-engine/commit/9839de33edc62fe495779385d98cf27e8649cc87))
* **deployment_set_automatic_update.py:** New distribution ([9839de3](https://github.com/nuvla/job-engine/commit/9839de33edc62fe495779385d98cf27e8649cc87))


### Bug Fixes

* fix helm update failing after failed install; improve oci vs http install/upgrade command ([#408](https://github.com/nuvla/job-engine/issues/408)) ([1ca4553](https://github.com/nuvla/job-engine/commit/1ca4553e6ab5ac6fcee16dea137e3724de593bd1))

## [4.7.1](https://github.com/nuvla/job-engine/compare/4.7.0...4.7.1) (2024-11-11)


### Minor Changes

* use LWPCookieJar format instead of MozillaCookieJar ([#405](https://github.com/nuvla/job-engine/issues/405)) ([7750e6b](https://github.com/nuvla/job-engine/commit/7750e6bf293e153415a10220f6a4125f64e75dd8))

## [4.7.0](https://github.com/nuvla/job-engine/compare/4.6.1...4.7.0) (2024-11-08)


### Features

* allow to provide cookies to authenticate to Nuvla ([#399](https://github.com/nuvla/job-engine/issues/399)) ([588cec1](https://github.com/nuvla/job-engine/commit/588cec139e5d55083d29192d895e06eb35e7728a))
* **helm-oci-repos:** support of Helm charts from OCI repos ([#402](https://github.com/nuvla/job-engine/issues/402)) ([f8ad021](https://github.com/nuvla/job-engine/commit/f8ad0216e72e9acd2880f93b212fbc30f4acbede))


### Bug Fixes

* **bulk-actions:** Progress divide by zero fix ([#401](https://github.com/nuvla/job-engine/issues/401)) ([07e4cad](https://github.com/nuvla/job-engine/commit/07e4cadbe25c5e2255cdd282226cfff09451b448))
* **BulkDeploymentSetApply:** Set api-endpoint attribute for deployments at update time ([#396](https://github.com/nuvla/job-engine/issues/396)) ([0b1e370](https://github.com/nuvla/job-engine/commit/0b1e37082080359ea751ab7c11d411e7d7a8a47c))
* **k8s:** NE update - secure get of values from install params ([1a713ac](https://github.com/nuvla/job-engine/commit/1a713ac9b2bc5e0b66deeeee37cf6fcbae5b19d6))
* **syntax-warn:** avoid syntax warning in the logs ([#400](https://github.com/nuvla/job-engine/issues/400)) ([899b3ed](https://github.com/nuvla/job-engine/commit/899b3edab41483f50745b2498fa99a4e02063c72))

## [4.6.1](https://github.com/nuvla/job-engine/compare/4.6.0...4.6.1) (2024-10-16)


### Bug Fixes

* Do not fail COE resource action job when some actions fail ([#393](https://github.com/nuvla/job-engine/issues/393)) ([850ec5a](https://github.com/nuvla/job-engine/commit/850ec5a6c71aefaece7d353a430052d7f254ca19))
* Improve return message when errors occur ([#394](https://github.com/nuvla/job-engine/issues/394)) ([45e0b12](https://github.com/nuvla/job-engine/commit/45e0b12d8a585d09a0c52a9d4f82c3ad20900866))

## [4.6.0](https://github.com/nuvla/job-engine/compare/4.5.2...4.6.0) (2024-10-11)


### Features

* **action:** Add COE docker resource management action(s) ([#388](https://github.com/nuvla/job-engine/issues/388)) ([8b35166](https://github.com/nuvla/job-engine/commit/8b35166e4dbebf9c4f0bcba60f81f1c0602295f2))

## [4.5.2](https://github.com/nuvla/job-engine/compare/4.5.1...4.5.2) (2024-10-07)


### Bug Fixes

* **kubernetes:** use endpoint from infrastructure-service when no local endpoint is available ([#390](https://github.com/nuvla/job-engine/issues/390)) ([c3e27f3](https://github.com/nuvla/job-engine/commit/c3e27f37f864433ead233a77e7d5efb44722b5ab))

## [4.5.1](https://github.com/nuvla/job-engine/compare/4.5.0...4.5.1) (2024-10-03)


### Minor Changes

* **deps:** allow any 3.x python version above 3.11 ([481b0cb](https://github.com/nuvla/job-engine/commit/481b0cbc3ad8cf9e531b8e210a78a7ec3a8f7ab0))

## [4.5.0](https://github.com/nuvla/job-engine/compare/4.4.0...4.5.0) (2024-10-02)


### Features

* add support for Python 3.12 ([#386](https://github.com/nuvla/job-engine/issues/386)) ([10c4689](https://github.com/nuvla/job-engine/commit/10c46897f7739764115eb632eacf58ca12551faa))


### Dependencies

* updated dependencies ([10c4689](https://github.com/nuvla/job-engine/commit/10c46897f7739764115eb632eacf58ca12551faa))

## [4.4.0](https://github.com/nuvla/job-engine/compare/4.3.1...4.4.0) (2024-09-25)


### Features

* **bulk_update_nuvlabox:** Support bulk update nuvlabox action ([#378](https://github.com/nuvla/job-engine/issues/378)) ([bf9b77e](https://github.com/nuvla/job-engine/commit/bf9b77ee71c54804643465c8869de10512c34d26))


### Bug Fixes

* **bulk_delete_deployment:** Support bulk delete deployment ([#382](https://github.com/nuvla/job-engine/issues/382)) ([22d4740](https://github.com/nuvla/job-engine/commit/22d474050cc35b3da4de576840172999b5d6a225))
* **bulk-action:** Report queued jobs and update success and failed list based on operation response status ([bf9b77e](https://github.com/nuvla/job-engine/commit/bf9b77ee71c54804643465c8869de10512c34d26))
* **K8s:** pod logs ([#381](https://github.com/nuvla/job-engine/issues/381)) ([46e532e](https://github.com/nuvla/job-engine/commit/46e532e001e3887472cd8f7b1d2b518eceee3511))
* **monitor_bulk_job:** Bugfix related to child job queries ([bf9b77e](https://github.com/nuvla/job-engine/commit/bf9b77ee71c54804643465c8869de10512c34d26))
* **monitor_bulk_job:** More info about what is being executed ([bf9b77e](https://github.com/nuvla/job-engine/commit/bf9b77ee71c54804643465c8869de10512c34d26))
* **nuvlaedge_k8s:** working upgrade of NE on K8s ([#385](https://github.com/nuvla/job-engine/issues/385)) ([81df7c7](https://github.com/nuvla/job-engine/commit/81df7c73d59f92e6f4b8a3636eeff640d995bf37))
* **workflows:** fix GIT_BUILD_TIME ([2adc27a](https://github.com/nuvla/job-engine/commit/2adc27ac891a9603b2fe2f55af10016248dad2c0))

## [4.3.1](https://github.com/nuvla/job-engine/compare/4.3.0...4.3.1) (2024-08-21)


### Bug Fixes

* **nuvlaedge_docker.py:** allow to update/cluster several NEs at the same time on the same docker  ([32ea4b1](https://github.com/nuvla/job-engine/commit/32ea4b1ed916c1581539bbdc50dbb0297c520d98))


### Dependencies

* nuvla-api ^4.0.2 ([1235958](https://github.com/nuvla/job-engine/commit/123595827f37b0b41a463886df874abeaca09cd6))
* updated indirect dependencies ([1235958](https://github.com/nuvla/job-engine/commit/123595827f37b0b41a463886df874abeaca09cd6))

## [4.3.0](https://github.com/nuvla/job-engine/compare/4.2.1...4.3.0) (2024-08-07)


### Features

* add management of Helm applications ([#354](https://github.com/nuvla/job-engine/issues/354)) ([d23844a](https://github.com/nuvla/job-engine/commit/d23844ad4020a0d424b5a61285bee5247893a247))


### Bug Fixes

* **cleanup_jobs:** Update action to remove canceled jobs and enhance filter string ([8b298a5](https://github.com/nuvla/job-engine/commit/8b298a5c0bd72e216da441197e5e187de639791b))


### Dependencies

* **docker-compose:** get docker compose from our own build to support docker config properly ([c1a725d](https://github.com/nuvla/job-engine/commit/c1a725d64ff6cabfd70e464821db32c1de0d4fcf))

## [4.2.1](https://github.com/nuvla/job-engine/compare/4.2.0...4.2.1) (2024-07-22)


### Bug Fixes

* timeout context manager: ignore timeout with a warning if not used from the main thread ([72cc9d1](https://github.com/nuvla/job-engine/commit/72cc9d1266b8888810a3f03f3cbae537c896757d))

## [4.2.0](https://github.com/nuvla/job-engine/compare/4.1.1...4.2.0) (2024-07-19)


### Features

* **deployments:** add TIMESTAMP and DATE_TIME environment variables ([7a4ea35](https://github.com/nuvla/job-engine/commit/7a4ea3504aae4fec9da2cd932d121c85713ea38b))

## [4.1.1](https://github.com/nuvla/job-engine/compare/4.1.0...4.1.1) (2024-07-01)


### Code Refactoring

* executor and actions ([#370](https://github.com/nuvla/job-engine/issues/370)) ([2225388](https://github.com/nuvla/job-engine/commit/22253887489e09c803b61d12aee381dec09ba11a))

## [4.1.0](https://github.com/nuvla/job-engine/compare/4.0.9...4.1.0) (2024-06-18)


### Bug Fixes

* **alpine:** v3.18 -&gt; v3.19 ([9ca626a](https://github.com/nuvla/job-engine/commit/9ca626a92a3e6f07c8ad5bfd1428761e7565b5a6))
* **ci:** Run devel workflow when Dockerfile content change ([#365](https://github.com/nuvla/job-engine/issues/365)) ([9ca626a](https://github.com/nuvla/job-engine/commit/9ca626a92a3e6f07c8ad5bfd1428761e7565b5a6))
* **coe_provision:** Action removed ([#368](https://github.com/nuvla/job-engine/issues/368)) ([61815ab](https://github.com/nuvla/job-engine/commit/61815ab40ec58d11fe63acb57eb6668ad4361371))
* **coe_start:** Action removed ([61815ab](https://github.com/nuvla/job-engine/commit/61815ab40ec58d11fe63acb57eb6668ad4361371))
* **coe_stop:** Action removed ([61815ab](https://github.com/nuvla/job-engine/commit/61815ab40ec58d11fe63acb57eb6668ad4361371))
* **coe_terminate:** Action removed ([61815ab](https://github.com/nuvla/job-engine/commit/61815ab40ec58d11fe63acb57eb6668ad4361371))
* **docker_machine:** Remove docker machine connector and binary ([61815ab](https://github.com/nuvla/job-engine/commit/61815ab40ec58d11fe63acb57eb6668ad4361371))
* **docker-cli-compose:** v2.17 -&gt; 2.27 ([9ca626a](https://github.com/nuvla/job-engine/commit/9ca626a92a3e6f07c8ad5bfd1428761e7565b5a6))
* **helm:** v3.11 -&gt; 3.14 ([9ca626a](https://github.com/nuvla/job-engine/commit/9ca626a92a3e6f07c8ad5bfd1428761e7565b5a6))


### Miscellaneous Chores

* release 4.1.0 ([7860b7d](https://github.com/nuvla/job-engine/commit/7860b7da47507cb2478d706ec09149b20b251edf))

## [4.0.9](https://github.com/nuvla/job-engine/compare/4.0.8...4.0.9) (2024-05-19)


### Bug Fixes

* deployment logs: include stderr when retrieving logs (docker) ([#364](https://github.com/nuvla/job-engine/issues/364)) ([1987c4c](https://github.com/nuvla/job-engine/commit/1987c4c9ed3db8136889bda2e26ad0a3fbb3e442))
* **docker_compose.py:** fix log retrival of stopped container and return an error message if the container is not found ([#362](https://github.com/nuvla/job-engine/issues/362)) ([8c9521d](https://github.com/nuvla/job-engine/commit/8c9521d913466f7885598a5e0619a1d2305311df))
* **nuvlabox.py:** nuvlabox_update() set NUVLA_ENDPOINT and NUVLA_ENDOINT_INSECURE env vars to the installer container ([#361](https://github.com/nuvla/job-engine/issues/361)) ([5b28af8](https://github.com/nuvla/job-engine/commit/5b28af8bb10afca8e8de87397799d72b9284f3ac))

## [4.0.8](https://github.com/nuvla/job-engine/compare/4.0.7...4.0.8) (2024-05-14)


### Bug Fixes

* **nuvlabox.py:** nuvlabox_update() do not fail if docker pull fails ([#359](https://github.com/nuvla/job-engine/issues/359)) ([7cc5e8b](https://github.com/nuvla/job-engine/commit/7cc5e8b8b752837498a970960507343a46658110))

## [4.0.7](https://github.com/nuvla/job-engine/compare/4.0.6...4.0.7) (2024-05-13)


### Bug Fixes

* kubernetes pod logs retrieval ([#358](https://github.com/nuvla/job-engine/issues/358)) ([d3324da](https://github.com/nuvla/job-engine/commit/d3324da75f1408dc8e821a749a68fb14c03d8a68))
* nuvlabox_releases.py: create release by default with view-data ACL for group/nuvla-anon ([4de2fb7](https://github.com/nuvla/job-engine/commit/4de2fb7a69e3e5c97529b3928aebfee41d11fc96))

## [4.0.6](https://github.com/nuvla/job-engine/compare/4.0.5...4.0.6) (2024-05-08)


### Bug Fixes

* add argument nuvlaedge-fs to executor ([#355](https://github.com/nuvla/job-engine/issues/355)) ([9611137](https://github.com/nuvla/job-engine/commit/9611137f8709b8cd4bedb43208aa612d41368e61))

## [4.0.5](https://github.com/nuvla/job-engine/compare/4.0.4...4.0.5) (2024-04-26)


### Bug Fixes

* **nuvla-api:** Upgrade nuvla-api to v4.0.0 ([156d61d](https://github.com/nuvla/job-engine/commit/156d61dd61df585136cc11e4fb3703154ab45c18))
* **nuvla:** Package nuvla extend search path to be able to import nuvla-api module ([156d61d](https://github.com/nuvla/job-engine/commit/156d61dd61df585136cc11e4fb3703154ab45c18))
* **requests:** Remove dependency, it will come from nuvla-api ([156d61d](https://github.com/nuvla/job-engine/commit/156d61dd61df585136cc11e4fb3703154ab45c18))

## [4.0.4](https://github.com/nuvla/job-engine/compare/4.0.3...4.0.4) (2024-04-04)


### Bug Fixes

* **nuvlabox:** fix issue with docker.tls.TLSConfig backward incompatible changes on v7.0.0 (updated in 72c8b6a) ([49a981c](https://github.com/nuvla/job-engine/commit/49a981cd013dd72db08a837e5ffb5d3c64033c9a))

## [4.0.3](https://github.com/nuvla/job-engine/compare/4.0.2...4.0.3) (2024-03-21)


### Bug Fixes

* **action_bulk_deployment_set_apply:** Take Operational Status files overrides into account when creating deployments of a DG ([69498b9](https://github.com/nuvla/job-engine/commit/69498b973bb758ec91a61ed766e22703a44a686a))
* **action_nuvlabox_releases:** Update github link from nuvlabox to nuvlaedge organization ([69498b9](https://github.com/nuvla/job-engine/commit/69498b973bb758ec91a61ed766e22703a44a686a))

## [4.0.2](https://github.com/nuvla/job-engine/compare/4.0.1...4.0.2) (2024-02-23)


### Bug Fixes

* **ci:** move job_engine back into nuvla package ([#342](https://github.com/nuvla/job-engine/issues/342)) ([e8de733](https://github.com/nuvla/job-engine/commit/e8de73396cddc282701f87b69d9f19f20ca64be9))

## [4.0.1](https://github.com/nuvla/job-engine/compare/4.0.0...4.0.1) (2024-02-21)


### Bug Fixes

* add check for job-engine v4 allowing up to 2 lower major versions ([709d6c1](https://github.com/nuvla/job-engine/commit/709d6c19c845b3ce5c94ace447229b1ff4b332e6))

## [4.0.0](https://github.com/nuvla/job-engine/compare/3.9.6...4.0.0) (2024-02-21)


### ⚠ BREAKING CHANGES

* Add new release workflow and python packaging tools

### Features

* Add new release workflow and python packaging tools ([6d9fcaa](https://github.com/nuvla/job-engine/commit/6d9fcaa23327495cea31eeff8c98a823f59c49d8))


### Bug Fixes

* **ci:** Add concurrency limits and selective paths and files for devel build ([138f5b6](https://github.com/nuvla/job-engine/commit/138f5b622fd7d71c29d2720c8a8abb45951bae99))
* **ci:** add concurrency to release so the current workflow is never canceled by itself ([38f5af0](https://github.com/nuvla/job-engine/commit/38f5af0bed9dc7f9fd9d4bcca280f9eb7b63e1fc))
* **ci:** fix bugged condition on notify job on release workflow ([e3f2483](https://github.com/nuvla/job-engine/commit/e3f2483e8fc9a17d9da8f76f62a54fc7beab10a3))
* **ci:** remove deprecated release.sh script ([f4e14e1](https://github.com/nuvla/job-engine/commit/f4e14e1a60abf633930bfeb4091c1094e939aeab))
* **ci:** second tag in release-docker job now points to latest ([9a00f6f](https://github.com/nuvla/job-engine/commit/9a00f6ffbbc619db858828ae0bf12bc045f101a1))
* **ci:** update cache action to v4 ([601f04d](https://github.com/nuvla/job-engine/commit/601f04d654b8a272c161504edefbb8d80c85f35e))
* **ci:** update setup-qemu-action to v4 ([ba12fa9](https://github.com/nuvla/job-engine/commit/ba12fa993cbd46e06ffe24ef2157b098be7a6b3b))


### Documentation

* add dev local unitest and image build instructions ([01971f7](https://github.com/nuvla/job-engine/commit/01971f743975e8799c6e5cb324a34082dc517176))

## [3.9.6](https://github.com/nuvla/job-engine/compare/v3.9.5...3.9.6) (2024-02-20)


### Bug Fixes

* trigger release ([add2635](https://github.com/nuvla/job-engine/commit/add2635a313685014d438a1ac6883d3351f1e09e))

## [3.9.5](https://github.com/nuvla/job-engine/compare/3.9.4...3.9.5) (2024-02-20)


### Features

* Add automated release with release-please ([798f6ba](https://github.com/nuvla/job-engine/commit/798f6bac76e79d66a2e64d33d1d7a2298d2572b7))

## [3.9.3] - 2023-12-21

- Job - Edit duplicated fix
- Bulk action - Refactor to make it more generic and set progress
- Bulk deployment set apply - Recompute operational status on job startup
- Container - Upgrade kubectl to v1.29

## [3.9.2] - 2023-12-14

- Deployment set apply - Deployment parameter value is not changing when user delete the value from the deployment group

## [3.9.1] - 2023-11-27

- docker_compose.py: fix bug in config function used in validate-docker-compose action
- deployment: provide NuvlaEdge IP addresses as output parameters
  - update output parameter "hostname" in deployment_state action
  - prevent having to pass "log" and "deployment" objects to method of DeploymentBase class
- monitor bulk jobs - Canceled jobs should be part of done jobs
- deployment set apply - use stop delete instead of force delete on deployment

## [3.9.0] - 2023-11-09

- Global - Use values new type of query (#299)
- Global - Review existing selects to avoid break with api-server changes
- Bulk deployment set action - Do not store todo (#301)
- bulk deployment action - Do not store todo

## [3.8.2] - 2023-11-01

- Deployment utils - Start, stop, update deployment actions will set deployment state to error when execution-mode is not mixed

## [3.8.1] - 2023-11-01

- Deployment state distributor - Optimize checking existing jobs and if existing parents

## [3.8.0] - 2023-10-27

- Kubernetes: fix reboot and update actions (#295)
- credential_check action - refactor swarm mode detection (#293)
- nuvlabox offline distributor - Replace nuvlabox status offline distributor (#288)

## [3.7.1] - 2023-10-02

- Update nuvlaedge on kubernetes via helm job (#292)
- Expose the original deployment parameters
- Re-write the helm command to use the nuvlaedge/nuvlaedge repo
- Add helm to container-lite

## [3.7.0] - 2023-09-25

- docker_stack.py - fix bug introduced in commit f757d27
- Feature - Passive monitoring of bulk jobs
- executor - Bulk job consumed and left in running state
- distributor - monitor bulk jobs
- action - Bulk deployment refactor
- action - Bulk base class refactor
- action - Cancel children jobs
- action - Deployment set force delete
- action - Deployment set delete
- action - Deployment set stop
- action - Deployemnt set update
- action - Deployemnt set start
- action - Deployemnt set apply class

## [3.6.0] - 2023-09-04

- Update to Docker Compose V2 and timeouts definition via environment variables
- Add the reboot function to NuvlaEdge Kubernetes
- ssh key addition for Kubernetes NuvlaEdge

## [3.5.2] - 2023-08-22

- Deployment set create - Resolve deployment set target
- Deployment actions - Improved detection of local endpoint and take it into account
- Deployment start - Create output parameters (from app) before starting the deployment
- Deployment start and update -Improved creation, update and retrieval of "hostname" parameter
- Deployment log fetch - Improve connector name retrieval through a property
- Kubernetes test - Fix when executed on a machine not on UTC timezone
- Docker compose - Give environment to all commands that might requires it
- Connectors - Refactor connectors and deployment related job actions

## [3.5.1] - 2023-07-21

- Updated nuvla-api from 3.0.8 to 3.0.9 to fix build issue with pyyaml and
  cython
- Distribution register usage record - Report for customer and subgroups
- Distribution register usage record new deployments - Faster report for
  customer and subgroups for new deployments

## [3.5.0] - 2023-07-16

### Changed

- Kubernetes logs - refactored and improved Kubernetes logs retrival
- Credential check action - handle properly local docker credentials

## [3.4.2] - 2023-07-04

### Changed

- NuvlaEdge installer - fix NuvlaEdge credential environment variables

## [3.4.1] - 2023-07-04

### Changed

- NuvlaEdge actions - ensure local docker socket is used in pull mode
- NuvlaEdge installer - allow to define image name with NE_IMAGE_INSTALLER environment variable

## [3.4.0] - 2023-06-27

### Changed

- Action nuvlabox_release - do not add GH release asset if it's not a docker-compose yaml file
- NuvlaEdge SSH and reboot actions - fix to work with the new NE base image
- NuvlaEdge base image - updated base_image and allow to edit it with environment variables

## [3.3.1] - 2023-06-23

### Changed

- Deployment set actions - Align with api server changes
- Container build - Fix docker hub organization selection

## [3.3.0] - 2023-06-12

### Changed

- Fix sonarcloud hotspots
- docker_machine.py: use https for portainer
- Dockerfile: enforce usage of HTTPS with curl
- nuvlabox.py: Fixed regex to filter ANSI Escape Sequences
- utils.py: replaced md5 by sha256 in unique_id function
- Dockerfile - modprobe script location changed
- Use local docker socket for pull jobs
- Use local Kubernetes API endpoint for pull jobs
- nuvlabox.py:
- get components with label "nuvlaedge" and not only with "nuvlabox"
- renamed some occurences of NuvlaBox to NuvlaEdge
- Updated containers base image to python:3.11-alpine3.18
- Development version numbers compliant with PEP440 version schemes (.dev instead of -SNAPSHOT)

## [3.2.7] - 2023-04-25

### Changed

- Docker compose - do not remove named volumes on stop

## [3.2.6] - 2023-04-24

### Changed

- Deployment set - actions updates (experimental)

## [3.2.5] - 2023-02-21

### Changed

- Nuvlabox decommission action - Delete resource log bugfix #257
- Credential check action - Swarm manager detection #255

## [3.2.4] - 2022-12-12

### Changed

- Add missing package "packaging" on nuvla/job Docker image

## [3.2.3] - 2022-12-06

### Changed

- Deployment set - Experimental feature

## [3.2.2] - 2022-10-10

### Changed

- Register-usage-record - distribution bugfix

## [3.2.1] - 2022-10-10

### Changed

- Register-usage-record - distribution filter canceled subscription bugfix

## [3.2.0] - 2022-09-28

### Changed

- Removed the generator of the individual notification subscriptions.
- Added build of the image for arm64.
- NuvlaEdge connector - add support for nuvlaedge org and main branch

## [3.1.2] - 2022-09-07

### Changed

- Nuvlabox status offline distributor - bugfix when an update of a NuvlaBox
  status fail, process was aborted #245
- NuvlaEdge connector - improve and fix update_nuvlabox_engine #244

## [3.1.1] - 2022-08-25

### Changed

- Notify-coupon-end - distribution check if job already exist
- Dockerfile - modprobe.sh moved in docker project repo

## [3.1.0] - 2022-07-18

### Added

- Refresh customer subscription cache - distribution

### Changed

- Register-usage-record - distribution filter canceled subscription
- Use common base image for all NE components

## [3.0.0] - 2022-06-29

### Added

- Register-usage-record - distribution
- Register-usage-record - action

### Changed

- Dependency - Remove Stripe api dependency
- Usage-report - distribution and execution deleted
- Trial-end - distributor adapt to api call change

## [2.20.2] - 2022-05-12

### Added

- Notify-coupon-end - distribution
- Notify-coupon-end - action

### Changed

- Trial-end - action use of handle-trial-end hook
- Trial-end - distribution use of list-trialing-subscription hook
- Dependency - nuvla-api 3.0.8

## [2.20.1] - 2022-05-04

### Changed

- Trial-end - distribution bugfix

## [2.20.0] - 2022-04-29

### Added

- Trial-end - distribution
- Trial-end - action

### Changed

- update nuvla-api dependency to v3.0.7

## [2.19.0] - 2022-03-08

### Added

- New reusable class for resource log fetch actions
- New action `fetch_nuvlabox_log` to fetch the logs from all components of an
  existing NuvlaBox

### Changed

- Rename all connectors to enhance code clarity
- Deployment utils - Move functions from deployment actions to utils module
- Docker compose - Do not fail if "docker-compose pull" fails during
  start/update of an app
- Docker compose validate action. BugFix on replacing the empty env variables so
  the check runs successfully when the compose file is correct.

## [2.18.0] - 2021-10-28

### Changed

- Docker machine - Google xargs bugfix
- NuvlaBox connector: allow to set advertised address on Swarm cluster creation
- Raise OperationNotAllowed exception when NuvlaBox operation's execution-mode
  is not supported

## [2.17.0] - 2021-10-21

### Added

- OpenStack driver for COE provisioning jobs

### Changed

- Refactor code for docker-machine creation
- Rolled back to using Python 3.8

## [2.16.3] - 2021-10-13

### Changed

- Fix Docker Compose timeout issue
- Fix Python 3.10 incompatible call to traceback.format_exception() in
  executor.py
- Changed base image tag to 3.10-alpine

## [2.16.2] - 2021-10-07

### Changed

- Fix deployment_state actions

## [2.16.1] - 2021-08-10

### Changed

- Make NuvlaBox Engine update job account for new update parameters

## [2.16.0] - 2021-08-04

### Changed

- Deployment - Mixed jobs shouldn't set deployment to error state on first try
- docker-compose-cli connector substitue env variables to avoid failures during
  start listing containers
- Execute_command separate stdout from stderr
- Update docker client to 20.10.7
- Distributions refactor multi-threaded
- Fix join-manager typo in action name
- Fix delete NuvlaBox cluster on last member leaving
- Generalize use of Docker Socket for NB pull jobs
- Add new legacy bind mount for NuvlaBox Update jobs
- Add environemnt vars to NuvlaBox Update sidecar container

## [2.15.2] - 2021-06-01

### Changed

- remove default local instantiation of Docker client for NuvlaBox connector

## [2.15.1] - 2021-05-12

### Added

- job-lite compatibility with arm64

## [2.15.0] - 2021-05-06

### Changed

- usage_report - remove usage report by number of deployments
- nuvlabox_decommission - remove online attribute when nuvlabox is
  decommissioned

### Added

- Action - Bulk force delete deployment
- Action - Bulk stop deployment
- Action - Clustering nuvlaboxes
- Action - Cleaning up leftover NuvlaBox clusters

## [2.14.2] - 2021-04-15

### Changed

- switch group - break job-engine lite fix
- container-lite: use alpine 3.12 to prevent issue with seccomp on Raspbian
  Buster
- docker_compose_cli_connector.py: fix custom docker registries (#178)

## [2.14.1] - 2021-04-09

### Changed

- docker compose cli connector - Bugfix custom registries

## [2.14.0] - 2021-04-09

### Added

- Action - Bulk update for deployment

### Changed

- Dependency - nuvla-api v3.0.3
- Switch group to group/nuvla_admin when api key is used for job-engine
- docker-compose validation - support port env var substitution

## [2.13.0] - 2021-02-22

### Changed

- nuvlabox_update job: add support for job payload attribute
- Fix: SSH key revoke action for the NuvlaBox fixed
- nuvlabox_update job: fix escaping of complex environment strings

## [2.12.1] - 2021-02-17

- Fix: include owner when subscription job searches for resources.

## [2.12.0] - 2021-02-16

### Added

- Distributor job to create/delete individual notification subscriptions.

### Changed

- Vulnerabilities database distributor exit on failure
- Nuvlabox releases distributor exit on failure
- Distributor - Exit-on-failure option

## [2.11.0] - 2021-02-09

### Added

- New distributor for setting nuvlabox status to offline
- New Job Engine Lite Docker image build, optimized for running jobs from within
  an infrastructure, with multi-arch support
- When a job with execution-mode=mixed fails, it get back in the job queue in
  pull-mode
- Create deployment_state jobs with execution-mode
- Add pause entrypoint

### Changed

- Credential check - support the UNKNOWN status for a credential check

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

- Action usage_report: bugfix on exclusion of deployments running on NuvlaBoxes
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
  configurable check intervals. This was done to reduce unnecessary load on the
  server and remote COEs.
- Jobs cleanup executor now goes via server API instead of directly to ES.

## [2.4.0] - 2020-07-06

### Added

- Added new actions for adding and revoking SSH keys from the NuvlaBox
- Deployment State job in push mode, as an entrypoint
- New job distributor and executor action for usage report
- New executor that provisions Docker Swarm and Kubernetes on AWS, Azure, Google
  Cloud, and Exoscale.

### Changed

- Dependency nuvla-api updated to v3.0.2
- Added cross-platform compatibility for Docker image
- Fixed Docker Compose deployment bug - allow containers to have internal ports
  that are not published to the host

## [2.3.16] - 2020-05-11

### Changed

- Deployment start - add NUVLA_DEPLOYEMT_UUID env var

## [2.3.15] - 2020-04-14

### Changed

- Docker cli connector - export node ip and ports when a service use host mode
  ports

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
- Connectors - docker api, docker cli and kubernetes cli support private
  registries
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

- Action service image state - consider nuvla as source of truth for deployed
  image version
- Action service and component image state - module path appended to the
  notification message

## [2.3.5] - 2019-09-04

### Added

- Service image state distributor and action added
- Component image state distributor and action added
- Deployment log fetch action added

### Changed

- Deployment action - Log message change
- Deployment state - Deployment state should not be set to state ERROR when this
  action fail
- Logging - remove thread name from logging since it's no more multi-threaded
- Successfully executed actions are in failed state because do_work isn't
  returning result code. This was the case for jobs_cleanup,
  nuvlabox_decommission, infrastructure_*
- Docker cli connector - when cacert is required connection fail fix
- Fix calculation of replicas.running to properly take into account the running
  task state
- Add deployment parameters to provide information about current Docker task:
  current.desired.state, current.state, and current.error.
- Fix misspelled method name in NuvlaBox decommissioning job that blocked
  deletion of NuvlaBox resources.

## [2.3.4] - 2019-08-07

### Changed

- Properly stop fix for job executor and and job distributor
- Nuvlabox decommission - Delete linked nuvlabox-peripheral
- Start deployment - When no volume options is set in deployment mounts, start
  deployment job is failing

## [2.3.3] - 2019-07-29

### Changed

- Connector Docker Cli - Fix when no ports are defined, the deploymnet fail

## [2.3.2] - 2019-07-25

### Changed

- Deployment actions - Put deployment in final state before raising the
  exception

## [2.3.1] - 2019-07-24

### Changed

- Fix in Deployment start component regression
- Deployment action do not cat exception to force full stack trace

## [2.3.0] - 2019-07-24

### Added

- Added support for start stop state deployment of subtype application
- Docker cli connector

### Changed

- When an error occur during execution of a job, the final state is set to '
  FAILED'

## [2.2.0] - 2019-06-20

### Added

- add script to restore zookeeper jobs from elasticsearch

### Changed

- Deployment - credential-id renamed parent
- Deployment parameter - field deployment/href renamed parent
- Executor is now mono-threaded. Use multiple executors to run multiple jobs in
  parallel.

## [2.1.0] - 2019-06-07

### Added

- Allow authentication with server via request headers
- Nuvlabox delete job
- Deployment state job

### Changed

- Reduce the sleep time to 30 seconds after an error when contacting the Nuvla
  server
- Deployment stop - delete credential on stop
- Update start deployment options to support restart policy conditions, cpu, ram
- Deployment code reorganization
- Release script fix
- Move reusable parts in util directory for actions
- Connector docker, stop container, if service not found should not return an
  error
- Deployment enhance exception management and always leave deployment in a final
  state
- Deployment start, stop, deployment resource changed

## [0.0.3] - 2019-04-18

### Changed

- first release of job container
