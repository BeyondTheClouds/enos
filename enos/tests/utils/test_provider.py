import unittest
from enos.utils.provider import *
import copy

class TestLoadConfig(unittest.TestCase):
    def test_load_config_with_topology(self):
        config = {
                'topology':{
                    'grp1': {
                        'a':{
                            'control': 1,
                            }
                        },
                    'grp[2-6]': {
                        'a':{
                            'compute': 10,
                            }
                        }
                    },
                'provider': 'test_provider'
                }
        expected_resources = {
                'resources': {
                    "a": {
                        "control": 1,
                        "compute": 50
                        }
                    }
                }
        conf = load_config(config, default_config={}, default_provider_config={})
        self.assertDictEqual(expected_resources['resources'], conf['resources'])


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
                default_provider_config=default_provider_config
                )
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
                default_provider_config=default_provider_config
                )
        self.assertDictEqual(expected, provider_config)

if __name__ == '__main__':
    unittest.main()
