import unittest
from engine.g5k_engine import G5kEngine, check_nodes, ROLE_DISTRIBUTION_MODE_STRICT
from execo.host import Host

class TestBuildRoles(unittest.TestCase):

    def setUp(self):
        self.engine = G5kEngine()
        self.engine.config = {
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

    def test_not_enough_nodes(self):
        self.engine.deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4"])
        with self.assertRaises(Exception):
            roles = self.engine.build_roles()
        
    def test_build_roles_same_number_of_nodes(self):
        self.engine.deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5", "a-6"])
        roles = self.engine.build_roles()
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(2, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["util"]))

    def test_build_roles_less_deployed_nodes(self):
        self.engine.deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5"])
        roles = self.engine.build_roles()
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(1, len(roles["compute"]))
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

    def test_enough_nodes_strict(self):
        nodes = [1, 2, 3, 4, 5, 6, 7]
        self.assertTrue(check_nodes(nodes, self.roles, ROLE_DISTRIBUTION_MODE_STRICT))

    def test_enough_nodes_not_strict(self):
        nodes = [1, 2, 3, 4, 5, 6, 7]
        self.assertTrue(check_nodes(nodes, self.roles, ""))

    def test_not_enough_nodes_strict(self):
        nodes = [1, 2, 3, 4, 5, 6]
        with self.assertRaises(Exception):
            check_nodes(nodes, self.roles, ROLE_DISTRIBUTION_MODE_STRICT)

    def test_not_enough_nodes_not_strict(self):
        nodes = [1, 2, 3, 4, 5]
        self.assertTrue(check_nodes(nodes, self.roles, ""))


            
            

if __name__ == '__main__':
    unittest.main()

