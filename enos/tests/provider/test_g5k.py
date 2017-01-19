import unittest
from enos.provider.g5k import *
from execo.host import Host

class TestBuildRoles(unittest.TestCase):

    def setUp(self):
        config = {
            "resources": {
                "a": {
                    "controller": 1,
                    "compute" : 2,
                    "network" : 1,
                    "storage" : 1,
                    "util"    : 1
                }
            }
        }
        self.provider = G5k()
        self.provider.config = config

    def test_not_enough_nodes(self):
        self.provider.deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4"])
        with self.assertRaises(Exception):
            roles = self.provider._build_roles()

    def test_build_roles_same_number_of_nodes(self):
        self.provider.deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5", "a-6"])
        roles = self.provider._build_roles()
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(2, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["util"]))

    def test_build_roles_less_deployed_nodes(self):
        self.provider.deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5"])
        roles = self.provider._build_roles()
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(1, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["util"]))
    
    def test_build_roles_with_multiple_clusters(self):
        self.provider.config = {
            "resources": {
                "a": {
                    "controller": 1,
                    "compute" : 2,
                    "network" : 1,
                    "storage" : 1,
                    "util"    : 1
                },
                "b": {
                    "compute": 2  
                 }
            }
        }
        self.provider.deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5", "a-6", "b-1", "b-2"])
        roles = self.provider._build_roles()
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(4, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["util"]))
    



class TestCheckNodes(unittest.TestCase):

    def setUp(self):
        self.roles = {
                "a": {
                    "controller": 1,
                    "compute" : 1,
                    "network" : 1,
                    "storage" : 1,
                    "util"    : 1
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
