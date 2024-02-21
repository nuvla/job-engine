# -*- coding: utf-8 -*-

from ..actions import action


@action('nuvlabox_cluster_cleanup')
class NBClusterCleanupJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def nuvlabox_cluster_cleanup(self):
        existing_clusters = self.api.search('nuvlabox-cluster').resources

        to_delete = []
        for cluster in existing_clusters:
            nuvlaboxes = cluster.data.get('nuvlabox-managers', []) + cluster.data.get('nuvlabox-workers', [])
            nodes = cluster.data.get('managers', []) + cluster.data.get('workers', [])
            if len(nuvlaboxes) == 0:
                # a cluster without NBs is not supported
                to_delete.append(cluster.id)
                continue

            underlying_nbs = self.api.search('nuvlabox-status',
                                             filter=' or '.join(['parent="%s"' % nbid for nbid in nuvlaboxes])).resources

            if len(underlying_nbs) == 0:
                # these NBs are gone, so should be the cluster
                to_delete.append(cluster.id)
                continue

            leftover = True
            for nb in underlying_nbs:
                # all it takes is for one NuvlaBox to still be in Swarm mode, and be part of that cluster
                if nb.data.get('cluster-id', '') == cluster.data.get('cluster-id') \
                        or nb.data.get('node-id') in nodes:
                    leftover = False
                    break

            if leftover:
                to_delete.append(cluster.id)

        warnings = []
        for del_cluster_id in to_delete:
            try:
                self.api.delete(del_cluster_id)
            except Exception as e:
                warnings.append(f'{del_cluster_id} - Reason: {str(e)}')

        msg = 'NuvlaBox Clusters cleanup finished.'

        if warnings:
            msg += 'Had issues deleting the following clusters:\n%s' % " \n".join(warnings)

        self.job.set_status_message(msg)

        return 0

    def do_work(self):
        return self.nuvlabox_cluster_cleanup()
