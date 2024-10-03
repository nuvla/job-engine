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

    def _execute_actions(self, actions: dict) -> int:
        """

        Args:
            actions:

        Returns:

        """
        docker_success = True
        k8s_success = True
        results = []
        for coe, actions in actions.items():
            if coe == "docker":
                connector: NuvlaBox = NuvlaBox(api=self.api, job=self.job)
                connector.connect()
                result: list[dict] = connector.handle_resources(actions)
                docker_success = all([r["success"] for r in result])
                results.extend(result)

            if coe == "kubernetes":
                ...

        self.job.set_status_message(json.dumps([r['message'] for r in results], indent=4))
        self.job.set_progress(90)

        return 0 if docker_success and k8s_success else 1

    def do_work(self):
        log.info("Job started for {}.".format(self.job["action"]))
        self.job.set_progress(10)

        try:
            return self._execute_actions(self.job["actions"])
        except Exception as ex:
            log.error("Failed to {0}: {1}".format(self.job["action"], ex))
            self.job.set_status_message(repr(ex))
            raise ex
