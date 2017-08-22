import unittest
from enos.utils.extra import *
from enos.utils.errors import *
from enos.provider.host import Host
import enos.utils.constants as const
import copy
import contextlib
import os, shutil
import tempfile
import mock
import ddt

class TestExpandGroups(unittest.TestCase):
    def test_expand_groups(self):
        grps = "grp[1-3]"
        expanded = expand_groups(grps)
        self.assertEqual(3, len(expanded))

    def test_expand_one_group(self):
        grps = "grp"
        expanded = expand_groups(grps)
        self.assertEqual(1, len(expanded))

    def test_expand_groups_with_weird_name(self):
        grps = "a&![,[1-3]"
        expanded = expand_groups(grps)
        self.assertEqual(3, len(expanded))


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
        self.assertEqual(1, len(roles["controller"]))
        self.assertEqual(1, len(roles["storage"]))
        self.assertEqual(2, len(roles["compute"]))
        self.assertEqual(1, len(roles["network"]))
        self.assertEqual(1, len(roles["util"]))

    def test_build_roles_one_less_deployed_nodes(self):
        deployed_nodes = map(lambda x: Host(x), ["a-1", "a-2", "a-3", "a-4", "a-5"])
        roles = build_roles(self.config, deployed_nodes, self.byCluster)
        self.assertEqual(1, len(roles["controller"]))
        self.assertEqual(1, len(roles["storage"]))
        self.assertEqual(1, len(roles["compute"]))
        self.assertEqual(1, len(roles["network"]))
        self.assertEqual(1, len(roles["util"]))

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
        self.assertEqual(1, len(roles["controller"]))
        self.assertEqual(1, len(roles["storage"]))
        self.assertEqual(4, len(roles["compute"]))
        self.assertEqual(1, len(roles["network"]))
        self.assertEqual(1, len(roles["util"]))

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
        self.assertEqual(4, len(roles["compute"]))
        self.assertEqual(1, len(roles["controller"]))
        self.assertEqual(1, len(roles["storage"]))

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
        self.assertEqual(2, len(roles["compute"]))
        self.assertEqual(1, len(roles["network"]))
        self.assertEqual(1, len(roles["control"]))
        # Check the consistency betwwen groups
        self.assertListEqual(sorted(roles["grp1"]), sorted(roles["control"] + roles["network"] + roles["util"]))
        self.assertListEqual(sorted(roles["grp2"] + roles["grp3"]), sorted(roles["compute"]))


class TestMakeProvider(unittest.TestCase):

    @staticmethod
    def __provider_env(provider_name):
        "Returns env with a provider key"
        return {"config": {"provider": provider_name}}

    @staticmethod
    def __provider_env_ext(provider_name):
        "Returns env with an extended provider key that may include options"
        return {"config": {"provider": {"type": provider_name}}}

    def test_make_g5k(self):
        "Tests the creation of G5k provider"
        from enos.provider.g5k import G5k
        self.assertIsInstance(make_provider(self.__provider_env('g5k')), G5k)
        self.assertIsInstance(make_provider(self.__provider_env_ext('g5k')), G5k)

    def test_make_vbox(self):
        "Tests the creation of Vbox provider"
        from enos.provider.enos_vagrant import Enos_vagrant
        self.assertIsInstance(make_provider(self.__provider_env('vagrant')), Enos_vagrant)
        self.assertIsInstance(make_provider(self.__provider_env_ext('vagrant')), Enos_vagrant)

    def test_make_static(self):
        "Tests the creation of Static provider"
        from enos.provider.static import Static
        self.assertIsInstance(make_provider(self.__provider_env('static')), Static)
        self.assertIsInstance(make_provider(self.__provider_env_ext('static')), Static)

    def test_make_unexist(self):
        "Tests the raise of error for unknown/unloaded provider"
        with self.assertRaises(ImportError):
            make_provider(self.__provider_env('unexist'))

class TestGenerateInventoryString(unittest.TestCase):
    def test_address(self):
        h = Host("1.2.3.4")
        role = "test"
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ControlPath=~/.ssh/%C' g5k_role=test", generate_inventory_string(h, role))

    def test_address_alias(self):
        h = Host("1.2.3.4", alias="alias")
        role = "test"
        self.assertEqual("alias ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ControlPath=~/.ssh/%C' g5k_role=test", generate_inventory_string(h, role))


    def test_address_user(self):
        h = Host("1.2.3.4", user="foo")
        role = "test"
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_user=foo ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ControlPath=~/.ssh/%C' g5k_role=test", generate_inventory_string(h, role))

    def test_address_gateway(self):
        h = Host("1.2.3.4", extra={'gateway': '4.3.2.1'})
        role = "test"
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ControlPath=~/.ssh/%C -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 4.3.2.1\"' g5k_role=test", generate_inventory_string(h, role))

    def test_address_gateway_same_user(self):
        h = Host("1.2.3.4", user="foo", extra={'gateway': '4.3.2.1'})
        role = "test"
        self.assertEqual("1.2.3.4 ansible_host=1.2.3.4 ansible_ssh_user=foo ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ControlPath=~/.ssh/%C -o ProxyCommand=\"ssh -W %h:%p -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -l foo 4.3.2.1\"' g5k_role=test", generate_inventory_string(h, role))


class TestGetTotalWantedMachines(unittest.TestCase):
    def test_get_total_wanted_machines(self):
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
        self.assertEqual(8, get_total_wanted_machines(config["resources"]))

class TestResourcesIterator(unittest.TestCase):
    def test_resources_iterator(self):
        config = {
            "resources": {
                "a": {
                    "controller": 1,
                    "network" : 1,
                    "storage" : 3,
                },
                "b": {
                    "compute": 2
                 }
            }
        }
        actual = []
        for l1, l2, l3 in gen_resources(config["resources"]):
            actual.append((l1, l2, l3))
        expected = [("a", "controller", 1),
                    ("a", "network", 1),
                    ("a", "storage", 3),
                    ("b", "compute", 2)]
        self.assertItemsEqual(expected, actual)


class TestLoadProviderConfig(unittest.TestCase):
    def test_load_provider_config_nest_type(self):
        provider_config = 'myprovider'
        expected = {
            'type': 'myprovider'
        }
        provider_config = load_provider_config(copy.deepcopy(provider_config))
        self.assertDictEqual(expected, provider_config)

    def test_load_provider_config_nest_type_with_defaults(self):
        provider_config = 'myprovider'
        default_provider_config = {
            'option1': 'value1',
            'option2': 'value2',
        }
        expected = {
            'type': 'myprovider',
            'option1': 'value1',
            'option2': 'value2',
        }
        provider_config = load_provider_config(
            copy.deepcopy(provider_config),
            default_provider_config=default_provider_config)
        self.assertDictEqual(expected, provider_config)

    def test_load_provider_config_with_defaults(self):
        provider_config = {
            'type': 'myprovider',
            'option1': 'myvalue1'
        }
        default_provider_config = {
            'option1': 'value1',
            'option2': 'value2',
        }
        expected = {
            'type': 'myprovider',
            'option1': 'myvalue1',
            'option2': 'value2',
        }
        provider_config = load_provider_config(
            copy.deepcopy(provider_config),
            default_provider_config=default_provider_config)
        self.assertDictEqual(expected, provider_config)

    def test_load_provider_config_with_missing_keys(self):
        from collections import OrderedDict

        provider_config = {
            'is-overrided1': 'overrided-value',
            'is-overrided2': 'overrided-value'
        }

        # Note: Go with an OrderedDict and its order preserving keys
        # extraction, rather than vanilla dict. OrderedDict makes the
        # assertRaisesRegexp reliable on the order of missing keys in
        # the error message.
        default_provider_config = OrderedDict([
            ('is-overrided1', None),
            ('missing-overriding1', None),
            ('is-overrided2', None),
            ('missing-overriding2', None),
            ('no-overriding-needed', False)])

        with self.assertRaisesRegexp(
                EnosProviderMissingConfigurationKeys,
                "\['missing-overriding1', 'missing-overriding2'\]"):
            load_provider_config(
                provider_config,
                default_provider_config)

class TestSSH(unittest.TestCase):
    longMessage = True
    hosts = [Host('1.2.3.4')]
    env = {'resultdir': 'foo/bar', 'inventory': 'foo/bar'}

    def test_wait_ssh_succeed(self):
        with mock.patch('enos.utils.extra.run_ansible',
                        new_callable=mock.Mock()) as m:
            m.return_value=None
            self.assertIsNone(wait_ssh(self.env, interval=0))

    def test_wait_ssh_eventually_succeed(self):
        with mock.patch('enos.utils.extra.run_ansible',
                        new_callable=mock.Mock()) as m:
            effects = [EnosUnreachableHostsError(self.hosts)
                       for i in range(1, 10)]
            effects.append(None)
            m.side_effect = effects
            self.assertIsNone(wait_ssh(self.env, retries=10, interval=0))

    def test_wait_ssh_fails(self):
        with self.assertRaisesRegexp(Exception, 'Maximum retries reached'),\
             mock.patch('enos.utils.extra.run_ansible',
                        new_callable=mock.Mock()) as m:
            m.side_effect=EnosUnreachableHostsError(self.hosts)
            wait_ssh(self.env, interval=0)


@ddt.ddt
class TestPathLoading(unittest.TestCase):
    longMessage = True

    def setUp(self):
        self.sourcedir = const.ENOS_PATH
        self.workdir = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.workdir)

    def assertPathEqual(self, p1, p2, msg=None):
        self.assertEqual(os.path.normpath(p1),
                         os.path.normpath(p2),
                         msg)

    @ddt.data(('/abs/path/to/inventory.sample',
               'inventories/inventory.sample'),
              ('/abs/path/to/workload/', 'workload/'))
    @ddt.unpack
    def test_seek_path(self, abspath, relpath):
        # Execution from the source directory
        with working_directory(self.sourcedir):
            self.assertPathEqual(seekpath(abspath),
                                 abspath,
                                 "Seeking for an %s defined "
                                 "with an absolute path should always "
                                 "return that path" % abspath)

            self.assertPathEqual(seekpath(relpath),
                                 os.path.join(const.ENOS_PATH, relpath),
                                 "Seeking for %s from the source directory"
                                 "should seek into enos source" % relpath)

        # Execution from a working directory
        with working_directory(self.workdir):
            self.assertPathEqual(seekpath(abspath),
                                 abspath,
                                 "Seeking for %s defined "
                                 "with an absolute path should always "
                                 "return that path" % abspath)

            self.assertPathEqual(seekpath(relpath),
                                 os.path.join(const.ENOS_PATH, relpath),
                                 "In absence of %s in the working "
                                 "directory, enos should seek for that one "
                                 "in sources" % relpath)

            # Build a fake `relpath` in the working directory and
            # check seekpath behaviour
            os.makedirs(os.path.dirname(relpath))
            os.path.lexists(relpath) or os.mknod(relpath)
            self.assertPathEqual(seekpath(relpath),
                                 os.path.join(self.workdir, relpath),
                                 "In presence of %s in the working directory,"
                                 "enos should take this one" % relpath)

    def test_seek_unexisting_path(self):
        unexisting = 'an/unexisting/path'

        with working_directory(self.sourcedir):
            with self.assertRaises(EnosFilePathError):
                seekpath(unexisting)

        with working_directory(self.workdir):
            with self.assertRaises(EnosFilePathError):
                seekpath(unexisting)


@contextlib.contextmanager
def working_directory(path):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.

    See,
    https://code.activestate.com/recipes/576620-changedirectory-context-manager/

    """
    prev_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


if __name__ == '__main__':
    unittest.main()
