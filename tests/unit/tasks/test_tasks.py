import tempfile
import unittest
from pathlib import Path

import enos.tasks as tasks
from enos.utils.errors import EnosUnknownProvider

PROVIDERS = [
    'g5k', 'vagrant:virtualbox', 'vagrant:libvirt',
    'chameleonkvm', 'chameleonbaremetal', 'openstack',
    'vmong5k', 'static']


class TestNewTask(unittest.TestCase):
    def test_reservation_yaml_file_exists(self):
        for provider_name in PROVIDERS:
            with tempfile.NamedTemporaryFile() as reservation_f, \
                 self.assertRaises(
                     FileExistsError,
                     msg='A reservation.yaml file that already exists '
                         'should not be automatically rewritten by the '
                         'program'):
                tasks.new(provider_name, reservation_f.name)

    def test_reservation_yaml_for_providers(self):
        # Generates a reservation.yaml file for all existing provider
        for provider_name in PROVIDERS:
            with tempfile.TemporaryDirectory() as dirname:
                output_path = Path(dirname) / 'reservation.yaml'
                tasks.new(provider_name, output_path)
                self.assertTrue(
                    output_path.exists(),
                    msg=f'Calling task.new for provider={provider_name} '
                        'should create a reservation.yaml file')

    def test_reservation_yaml_for_unexisting_provider(self):
        # Generates a reservation.yaml file an unexisting provider
        with tempfile.TemporaryDirectory() as dirname, \
             self.assertRaises(
                 EnosUnknownProvider,
                 msg='Generating a reservation.yaml file for a non existing '
                     'provider should fail with EnosUnknownProvider'):
            output_path = Path(dirname) / 'reservation.yaml'
            tasks.new('unexist', output_path)


if __name__ == '__main__':
    unittest.main()
