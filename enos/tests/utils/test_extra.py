import unittest
from enos.utils.extra import *
from execo import Host

class TestExpandGroups(unittest.TestCase):
    def test_expand_groups(self):
        grps = "grp[1-3]"
        expanded = expand_groups(grps)
        self.assertEquals(3, len(expanded))

    def test_expand_one_group(self):
        grps = "grp"
        expanded = expand_groups(grps)
        self.assertEquals(1, len(expanded))

    def test_expand_groups_with_weird_name(self):
        grps = "a&![,[1-3]"
        expanded = expand_groups(grps)
        self.assertEquals(3, len(expanded))


class TestBuildRoles(unittest.TestCase):

    def setUp(self):
        self.config = {
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

    def byCluster(self, n):
        """G5K provider"""
        return n.address.split('-')[0]

    def bySize(self, n):
        """Vagrant provider"""
        return n["size"]

#    def test_not_enough_nodes(self):
#        deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4"])
#        with self.assertRaises(Exception):
#            roles = build_roles(self.config, deployed_nodes, self.byCluster)

    def test_build_roles_same_number_of_nodes(self):
        deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5", "a-6"])
        roles = build_roles(self.config, deployed_nodes, self.byCluster)
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(2, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["util"]))

    def test_build_roles_one_less_deployed_nodes(self):
        deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5"])
        roles = build_roles(self.config, deployed_nodes, self.byCluster)
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(1, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["util"]))

    def test_build_roles_with_multiple_clusters(self):
        config = {
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
        deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5", "a-6", "b-1", "b-2"])
        roles = build_roles(config, deployed_nodes, self.byCluster)
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))
        self.assertEquals(4, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["util"]))

    def test_build_roles_with_multiple_sizes(self):
        config = {
            "resources": {
                "a": {
                    "controller": 1,
                },
                "b": {
                    "compute": 2
                 },
                "c": {
                    "compute": 2
                },
                "d": {
                    "storage": 1
                 }
            }
        }
        deployed_nodes = map(lambda x: {
            "size": x[0],
            "name": x
        }, ["a1", "b1", "b2", "c1", "c2", "d1"])

        roles = build_roles(config, deployed_nodes, self.bySize)
        self.assertEquals(4, len(roles["compute"]))
        self.assertEquals(1, len(roles["controller"]))
        self.assertEquals(1, len(roles["storage"]))

    def test_build_roles_with_topology(self):
        config = {
            "topology": {
                "grp1": {
                    "a":{
                        "control": 1,
                        "network": 1,
                        "util": 1
                        }
                    },
                "grp2": {
                    "a":{
                        "compute": 1,
                        }
                    },
                "grp3": {
                    "a":{
                        "compute": 1,
                        }
                    }
                },
               # resources is an aggregated view of the topology
               "resources": {
                   "a": {
                       "control": 1,
                       "network": 1,
                       "util": 1,
                       "compute": 2
                    }
               }
            }
        deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5"])
        roles = build_roles(config, deployed_nodes, self.byCluster)
        # Check the sizes
        self.assertEquals(2, len(roles["compute"]))
        self.assertEquals(1, len(roles["network"]))
        self.assertEquals(1, len(roles["control"]))
        # Check the consistency betwwen groups
        self.assertListEqual(sorted(roles["grp1"]), sorted(roles["control"] + roles["network"] + roles["util"]))
        self.assertListEqual(sorted(roles["grp2"] + roles["grp3"]), sorted(roles["compute"]))


class TestMakeProvider(unittest.TestCase):

    # TODO: test raises error
    def __provider_env(self, provider_name):
        "Returns env with a provider key"
        return {"config": {"provider": provider_name}}

    def __provider_env_ext(self, provider_name):
        "Returns env with an extended provider key that may include options"
        return {"config": {"provider": {"type": provider_name}}}

    def test_make_g5k(self):
        "Tests the creation of G5k provider"
        from enos.provider.g5k import G5k
        self.assertIsInstance(make_provider(self.__provider_env('g5k')), G5k)
        self.assertIsInstance(make_provider(self.__provider_env_ext('g5k')), G5k)

    def test_make_vbox(self):
        "Tests the creation of Vbox provider"
        from enos.provider.vbox import Vbox
        self.assertIsInstance(make_provider(self.__provider_env('vbox')), Vbox)
        self.assertIsInstance(make_provider(self.__provider_env_ext('vbox')), Vbox)

    def test_make_unexist(self):
        "Tests the raise of error for unknown/unloaded provider"
        with self.assertRaises(ImportError):
            make_provider(self.__provider_env('unexist'))



if __name__ == '__main__':
    unittest.main()
