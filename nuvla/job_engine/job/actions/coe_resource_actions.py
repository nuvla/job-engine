import json
import logging

from ..job import Job
from ..actions import action
from ...connector.coe_resources import DockerCoeResources

action_name = "coe_resource_actions"

log = logging.getLogger(action_name)


@action(action_name, True)
class COEResourceActionsJob:
    def __init__(self, job):
        self.job: Job = job
        self.api = job.api

    def _execute_actions(self, str_actions: str) -> int:
        """

        Args:
            str_actions:

        Returns:

        """
        if not self.job.is_in_pull_mode:
            self.job.set_status_message("Job is only available in pull mode")
            return 1

        actions = self._get_actions_from_string(str_actions)

        docker_success = True
        k8s_success = True
        results = {
            "docker": [],
        }
        for coe, actions in actions.items():
            if coe == "docker":
                connector: DockerCoeResources = DockerCoeResources()
                result: list[dict] = connector.handle_resources(actions)
                docker_success = all([r["success"] for r in result])
                results["docker"].extend(result)
            else:

                coe = "unknown" if coe is None or coe == "" else coe

                results[coe] = [
                    {
                        "success": False,
                        "return-code": 500,
                        "message": f"Actions not supported for {coe}"
                    }
                ]

            # if coe == "kubernetes":
            #     ...

        self.job.set_status_message(json.dumps(results, indent=4))
        self.job.set_progress(90)

        return 0 if docker_success and k8s_success else 1

    @staticmethod
    def _get_actions_from_string(actions: str) -> dict:
        """

        Args:
            actions:

        Returns:

        """
        try:
            return json.loads(actions)
        except json.JSONDecodeError as ex:
            log.error("Failed to decode actions: {0}".format(ex))
            raise ex

    def do_work(self):
        log.info("Job started for {}.".format(self.job["action"]))
        self.job.set_progress(10)

        try:
            return self._execute_actions(self.job["payload"])
        except Exception as ex:
            log.error("Failed to {0}: {1}".format(self.job["action"], ex))
            self.job.set_status_message(repr(ex))
            raise ex
