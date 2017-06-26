from enos.provider.static import Static
import unittest


class TestBuildResources(unittest.TestCase):
    def test_build_resources(self):
        def _uniformize(the_dict):
            "Sorts table values of `the_dict` to make order predictable."
            return {k: sorted(v) for k, v in the_dict.items()}

        topology = {
          "grp1": {
            "compute": {
              "address": "ip1"
            },
            "control": {
              "address": "ip2"
            }
          },
          "grp2": {
            "compute": {
              "address": "ip3"
            }
          }
        }

        resources_expected = {
            "control": [{"address": "ip2"}],
            "compute": [{"address": "ip1"}, {"address": "ip3"}],
            "grp1": [{"address": "ip1"}, {"address": "ip2"}],
            "grp2": [{"address": "ip3"}]
        }

        resources_actual = Static().topology_to_resources(topology)

        self.assertDictEqual(_uniformize(resources_expected),
                             _uniformize(resources_actual))
