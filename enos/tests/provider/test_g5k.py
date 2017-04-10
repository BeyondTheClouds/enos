from enos.provider.g5k import G5k, ROLE_DISTRIBUTION_MODE_STRICT
from execo.host import Host
from execo_g5k import OarSubmission
from execo_g5k import api_utils as api
import mock
import unittest

class TestCheckNodes(unittest.TestCase):

    def setUp(self):
        self.roles = {
                "a": {
                    "controller": 1,
                    "compute": 1,
                    "network": 1,
                    "storage": 1,
                    "util": 1
                },
                "b": {
                    "compute": 2
                }
            }
        self.provider = G5k()

    def test_enough_nodes_strict(self):
        nodes = [1, 2, 3, 4, 5, 6, 7]
        self.assertTrue(self.provider._check_nodes(nodes, self.roles, ROLE_DISTRIBUTION_MODE_STRICT))

    def test_enough_nodes_not_strict(self):
        nodes = [1, 2, 3, 4, 5, 6, 7]
        self.assertTrue(self.provider._check_nodes(nodes, self.roles, ""))

    def test_not_enough_nodes_strict(self):
        nodes = [1, 2, 3, 4, 5, 6]
        with self.assertRaises(Exception):
            self.provider._check_nodes(nodes, self.roles, ROLE_DISTRIBUTION_MODE_STRICT)

    def test_not_enough_nodes_not_strict(self):
        nodes = [1, 2, 3, 4, 5]
        self.assertTrue(self.provider._check_nodes(nodes, self.roles, ""))


class TestCreateReservation(unittest.TestCase):
    def equalsJobSpecs(self, expected, actual):
        # We only consider some attribute here, assuming it's enough
        e = map(lambda (oar, site): (oar.resources, oar.name, site), expected)
        a = map(lambda (oar, site): (oar.resources, oar.name, site), actual)
        self.assertItemsEqual(e, a)

    def test_create_reservation_no_vlan(self):
        conf = {
            'resources': {
                'a': {
                    'controller': 1,
                    'compute': 1,
                    'network': 1,
                 }
            },
            'provider': {
                'name': 'test',
                'vlans': {}
            }
        }
        api.get_cluster_site = mock.Mock(return_value="mysite")
        provider = G5k()
        jobs_specs = provider._create_reservation(conf)
        expected = [(OarSubmission("{cluster='a'}/nodes=3", name='test'), 'mysite')]
        self.equalsJobSpecs(expected, jobs_specs)

    def test_create_reservation_vlan_same_site(self):
        conf = {
            'resources': {
                'a': {
                    'controller': 1,
                    'compute': 1,
                    'network': 1,
                 }
            },
            'provider': {
                'name': 'test',
                'vlans': {'mysite': "{type='kavlan'}/vlan=1"},
            }
        }
        api.get_cluster_site = mock.Mock(return_value='mysite')
        provider = G5k()
        jobs_specs = provider._create_reservation(conf)
        expected = [(OarSubmission("{cluster='a'}/nodes=3+{type='kavlan'}/vlan=1", name='test'), 'mysite')]
        self.equalsJobSpecs(expected, jobs_specs)

    def test_create_reservation_vlan_different_site(self):
        conf = {
            'resources': {
                'a': {
                    'controller': 1,
                    'compute': 1,
                    'network': 1,
                 }
            },
            'provider': {
                'name': 'test',
                'vlans': {'myothersite': "{type='kavlan'}/vlan=1"},
            }
        }
        api.get_cluster_site = mock.Mock(return_value='mysite')
        provider = G5k()
        jobs_specs = provider._create_reservation(conf)
        expected = [
                (OarSubmission("{cluster='a'}/nodes=3", name='test'), 'mysite'),
                (OarSubmission("{type='kavlan'}/vlan=1", name='test'), 'myothersite')]
        self.equalsJobSpecs(expected, jobs_specs)

    def test_create_reservation_different_site(self):
        conf = {
            'resources': {
                'a': {
                    'controller': 1,
                    'compute': 1,
                    'network': 1,
                 },
                'b' : {
                    'compute': 10
                }
            },
            'provider': {
                'name': 'test',
                'vlans': {}
            }
        }
        api.get_cluster_site = mock.Mock()
        api.get_cluster_site.side_effect = ['mysite', 'myothersite']
        provider = G5k()
        jobs_specs = provider._create_reservation(conf)
        expected = [
                (OarSubmission("{cluster='a'}/nodes=3", name='test'), 'mysite'),
                (OarSubmission("{cluster='b'}/nodes=10", name='test'), 'myothersite')]
        self.equalsJobSpecs(expected, jobs_specs)


