
from .connector import Connector

from nuvla.connector.docker_machine_connector import DockerMachineConnector


def instantiate_from_cimi(infra_service_coe: dict, cloud_driver_credential: dict):
    return COECluster(
        driver_credential=cloud_driver_credential,
        driver_name=cloud_driver_credential['subtype'].split('-')[-1],
        machine_base_name=infra_service_coe['id'].split('/')[1])


class COECluster(Connector):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.driver_name = self.kwargs.get("driver_name")
        self.cloud_driver_credential = self.kwargs["driver_credential"]
        self.machine_base_name = self.kwargs.get("machine_base_name").replace(" ", "-")

    def create(self, multiplicity):
        nodes = []
        dmc = DockerMachineConnector(
            driver_credential=self.cloud_driver_credential,
            driver_name=self.driver_name,
            machine_base_name=f'{self.machine_base_name}-master-1')
        master = dmc.start()
        nodes.append(master)
        for i in range(1, multiplicity):
            dmc = DockerMachineConnector(
                driver_credential=self.cloud_driver_credential,
                driver_name=self.driver_name,
                machine_base_name=f'{self.machine_base_name}-worker-{i}')
            worker = dmc.start()
            nodes.append(worker)

    def destroy(self):
        pass

    def stop(self):
        pass

    def start(self):
        pass

    def update(self):
        pass