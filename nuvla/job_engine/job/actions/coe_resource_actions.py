import json
import logging

from ..job import Job
from ..actions import action
from ...connector.nuvlaedge_docker import NuvlaBox

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
        actions = self._get_actions_from_string(str_actions)

        docker_success = True
        k8s_success = True
        results = []
        for coe, actions in actions.items():
            if coe == "docker":
                connector: NuvlaBox = NuvlaBox(api=self.api, job=self.job, nuvlabox_id=self.job['target-resource']['href'])
                connector.connect()
                result: list[dict] = connector.handle_resources(actions)
                docker_success = all([r["success"] for r in result])
                results.extend(result)

            if coe == "kubernetes":
                ...

        self.job.set_status_message(json.dumps([r['message'] for r in results], indent=4))
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
