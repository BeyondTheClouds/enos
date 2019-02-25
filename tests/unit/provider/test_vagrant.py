from enos.provider.enos_vagrant import _build_enoslib_conf
import operator
import unittest


# Addding assertCountEqual in python 2
if not hasattr(unittest.TestCase, 'assertCountEqual'):
    unittest.TestCase.assertCountEqual = unittest.TestCase.assertItemsEqual


class TestGenEnoslibRoles(unittest.TestCase):

    def test_with_resources(self):
        resources = {
            "flavor1": {
                "control": "1"
            },
            "flavor2": {
                "compute": "1",
                "network": "1"
            }
        }
        enoslib_conf = _build_enoslib_conf({"resources": resources})

        machines = sorted(enoslib_conf["resources"]["machines"],
                          key=operator.itemgetter("roles"))
        self.assertEqual(3, len(machines))
        self.assertEqual(["default_group", "compute"], machines[0]["roles"])
        self.assertEqual(["default_group", "control"], machines[1]["roles"])
        self.assertEqual(["default_group", "network"], machines[2]["roles"])
        self.assertEqual("flavor2", machines[0]["flavour"])
        self.assertEqual("flavor1", machines[1]["flavour"])
        self.assertEqual("flavor2", machines[2]["flavour"])



    def test_with_topology(self):
        resources_1 = { "flavor1": { "control": "1" } }
        resources_2 = { "flavor2": { "compute": "1", "network": "1" } }
        topology = {
            "grp1": resources_1,
            "grp2": resources_2
        }
        enoslib_conf = _build_enoslib_conf({"topology": topology})

        machines = sorted(enoslib_conf["resources"]["machines"],
                          key=operator.itemgetter("roles"))

        self.assertEqual(3, len(machines))
        self.assertCountEqual(["grp1", "control"], machines[0]["roles"])
        self.assertCountEqual(["grp2", "compute"], machines[1]["roles"])
        self.assertCountEqual(["grp2", "network"], machines[2]["roles"])
        self.assertEqual("flavor1", machines[0]["flavour"])
        self.assertEqual("flavor2", machines[1]["flavour"])
        self.assertEqual("flavor2", machines[2]["flavour"])


    def test_with_expanded_topology(self):
        resources_1 = { "flavor1": { "control": "1" } }
        resources_2 = { "flavor2": { "compute": "1", "network": "1" } }
        topology = {
            "grp1": resources_2,
            "grp[2-10]": resources_1,
        }
        enoslib_conf = _build_enoslib_conf({"topology": topology})

        machines = sorted(enoslib_conf["resources"]["machines"],
                          key=operator.itemgetter("roles"))

        self.assertEqual(11, len(machines))

