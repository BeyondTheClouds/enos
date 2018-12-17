import operator
import unittest

import mock

from enos.provider.g5k import (_build_enoslib_conf, _count_common_interfaces, _get_sites)

PROVIDER = {'type': 'g5k',
            'job_name': 'enos-test'}

INTERFACES = {"paravance": ["link01", "link02"],
              "parapluie": ["link01"]}

CLUSTERS_SITES = { "paravance": "rennes", "grisou": "nancy" }


class TestGenEnoslibRoles(unittest.TestCase):

    @mock.patch("enoslib.infra.enos_g5k.api.get_clusters_interfaces",
                return_value=INTERFACES)
    def test_count_common_interfaces(self, mock_get_clusters_interfaces):
        result = _count_common_interfaces(['paravance', 'parasilo'])
        self.assertEqual(1, result)

    @mock.patch("enoslib.infra.enos_g5k.api.get_clusters_sites",
                return_value=CLUSTERS_SITES)
    def test_get_sites(self, mock_get_clusters_sites):
        result = _get_sites(["paravance", "grisou"])
        self.assertEqual(2, len(result))

    @mock.patch("enos.provider.g5k._get_sites", return_value={"site1"})
    @mock.patch("enos.provider.g5k._count_common_interfaces", return_value=2)
    def test_with_resources(self, mock_count_common_interfaces, mock_get_sites):
        resources = {
            'paravance': {
                'control': 1,
                'compute': 1,
                'network': 1,
            }
        }

        conf = {
            'resources': resources,
            'provider': PROVIDER
        }

        enoslib_conf = _build_enoslib_conf(conf)
        self.assertIsNotNone(enoslib_conf)

        machines = sorted(enoslib_conf['resources']['machines'],
                          key=operator.itemgetter('roles'))
        self.assertEquals(3, len(machines))
        self.assertEqual(['default_group', 'compute'], machines[0]['roles'])
        self.assertEqual(['default_group', 'control'], machines[1]['roles'])
        self.assertEqual(['default_group', 'network'], machines[2]['roles'])

        networks = sorted(enoslib_conf['resources']['networks'],
                          key=operator.itemgetter('id'))
        self.assertEquals(2, len(networks))
        self.assertCountEqual(['network_interface'], networks[1]['roles'])
        self.assertCountEqual(['neutron_external_interface'], networks[0]['roles'])

        self.assertEquals('site1', networks[1]['site'])
        self.assertEquals('site1', networks[0]['site'])

    @mock.patch("enos.provider.g5k._get_sites", return_value={"site1"})
    @mock.patch("enos.provider.g5k._count_common_interfaces", return_value=1)
    def test_with_resources_one_network(self, mock_count_common_interfaces, mock_get_sites):
        resources = {
            'parapluie': {
                'control': 1,
                'network': 1,
            }
        }

        conf = {
            'resources': resources,
            'provider': PROVIDER
        }

        enoslib_conf = _build_enoslib_conf(conf)
        self.assertIsNotNone(enoslib_conf)

        machines = sorted(enoslib_conf['resources']['machines'],
                          key=operator.itemgetter('roles'))
        self.assertEquals(2, len(machines))
        self.assertEqual([], machines[0]['secondary_networks'])

        networks = sorted(enoslib_conf['resources']['networks'],
                          key=operator.itemgetter('id'))
        self.assertEquals(1, len(networks))
        self.assertCountEqual(['network_interface'], networks[0]['roles'])
        self.assertEquals('site1', networks[0]['site'])

    @mock.patch("enos.provider.g5k._get_sites", return_value={"site1"})
    @mock.patch("enos.provider.g5k._count_common_interfaces", return_value=2)
    def test_with_topology(self, _count_common_interfaces, mock_get_sites):
        topology = {
            "group-0": {
                "paravance": {
                    "control": 1,
                    "network": 1,
                    "storage": 1,
                }
            },
            "group-1": {
                "parasilo": {
                    "compute": 10
                }
            },
            "group-2": {
                "parasilo": {
                    "compute": 10
                }
            }
        }

        conf = {
            'topology': topology,
            'provider': PROVIDER
        }

        enoslib_conf = _build_enoslib_conf(conf)
        self.assertIsNotNone(enoslib_conf)

        machines = sorted(enoslib_conf['resources']['machines'],
                          key=operator.itemgetter('roles'))
        self.assertEquals(5, len(machines))
        self.assertEqual(['group-0', 'control'], machines[0]['roles'])
        self.assertEqual(['group-0', 'network'], machines[1]['roles'])
        self.assertEqual(['group-0', 'storage'], machines[2]['roles'])
        self.assertEqual(['group-1', 'compute'], machines[3]['roles'])
        self.assertEqual(['group-2', 'compute'], machines[4]['roles'])

        networks = sorted(enoslib_conf['resources']['networks'],
                          key=operator.itemgetter('id'))
        self.assertEquals(2, len(networks))
        self.assertEquals('site1', networks[1]['site'])
        self.assertEquals('site1', networks[0]['site'])

    @mock.patch("enos.provider.g5k._get_sites", return_value={"site1"})
    @mock.patch("enos.provider.g5k._count_common_interfaces", return_value=1)
    def test_with_topology_with_ranges(self, _count_common_interfaces, mock_get_sites):
        topology = {
            'group-1': {
                'parapluie': {
                    'control': 2,
                    'network': 1
                    },
                'parasilo': {
                    'storage': 1
                    }
            },
            'group-[2-6]': {
                'paravance': {
                    'compute': 7
                }
            }
        }

        conf = {
            'topology': topology,
            'provider': PROVIDER
        }

        enoslib_conf = _build_enoslib_conf(conf)
        self.assertIsNotNone(enoslib_conf)

        machines = enoslib_conf['resources']['machines']
        self.assertEquals(8, len(machines))

        nodes = sum([x['nodes'] for x in machines])
        self.assertEquals(39, nodes)
