from enos.provider.static import _build_enoslib_conf
import operator
import unittest


class TestGenEnoslibRoles(unittest.TestCase):

    def test_with_resources(self):
        resources = {
            "compute": [{"address": "1.2.3.4", "alias": "enos-0"}] ,
            "control": [{"address": "1.2.3.5", "alias": "enos-1"}] ,
            "network": [{"address": "1.2.3.6", "alias": "enos-2"}] ,
        }
        conf = {
            "provider": {"networks": []},
            "resources": resources
        }
        enoslib_conf = _build_enoslib_conf(conf)
        machines = sorted(enoslib_conf["resources"]["machines"],
                          key=operator.itemgetter("address"))
        self.assertEqual(["1.2.3.4", "1.2.3.5", "1.2.3.6"],
                         [m["address"] for m in machines])
        self.assertEqual(["default_group", "compute"], machines[0]["roles"])
        self.assertEqual(["default_group", "control"], machines[1]["roles"])
        self.assertEqual(["default_group", "network"], machines[2]["roles"])


    def test_with_topology(self):
        resources_1 = {
            "compute": [{"address": "1.2.3.4", "alias": "enos-0"}] ,
            "control": [{"address": "1.2.3.5", "alias": "enos-1"}] ,
        }
        resources_2 = {
            "network": [{"address": "1.2.3.6", "alias": "enos-2"}] ,
        }

        conf = {
            "provider": {"networks": []},
            "topology": {"grp1": resources_1, "grp2": resources_2}
        }

        enoslib_conf = _build_enoslib_conf(conf)
        machines = sorted(enoslib_conf["resources"]["machines"],
                          key=operator.itemgetter("address"))
        self.assertEqual(["1.2.3.4", "1.2.3.5", "1.2.3.6"],
                         [m["address"] for m in machines])
        self.assertEqual(["grp1", "compute"], machines[0]["roles"])
        self.assertEqual(["grp1", "control"], machines[1]["roles"])
        self.assertEqual(["grp2", "network"], machines[2]["roles"])
