import unittest
import enos.utils.extra as xenos
from enos.utils.errors import (EnosProviderMissingConfigurationKeys,
                               EnosFilePathError)
import enos.utils.constants as C
import copy
import contextlib
import os
import pathlib
import shutil
import tempfile
import ddt


class TestMakeProvider(unittest.TestCase):

    @staticmethod
    def __provider_env(provider_name):
        "Returns env with a provider key"
        return provider_name

    @staticmethod
    def __provider_env_ext(provider_name):
        "Returns env with an extended provider key that may include options"
        return {"type": provider_name}

    def test_make_g5k(self):
        "Tests the creation of G5k provider"
        from enos.provider.g5k import G5k
        self.assertIsInstance(
            xenos.make_provider(self.__provider_env('g5k')), G5k)
        self.assertIsInstance(
            xenos.make_provider(self.__provider_env_ext('g5k')), G5k)

    def test_make_vbox(self):
        "Tests the creation of Vbox provider"
        from enos.provider.enos_vagrant import Enos_vagrant
        self.assertIsInstance(
            xenos.make_provider(self.__provider_env('vagrant')), Enos_vagrant)
        self.assertIsInstance(
            xenos.make_provider(self.__provider_env_ext('vagrant')),
            Enos_vagrant)

    def test_make_static(self):
        "Tests the creation of Static provider"
        from enos.provider.static import Static
        self.assertIsInstance(
            xenos.make_provider(self.__provider_env('static')), Static)
        self.assertIsInstance(
            xenos.make_provider(self.__provider_env_ext('static')), Static)

    def test_make_unexist(self):
        "Tests the raise of error for unknown/unloaded provider"
        with self.assertRaises(ImportError):
            xenos.make_provider(self.__provider_env('unexist'))


class TestLoadProviderConfig(unittest.TestCase):
    def test_load_provider_config_nest_type(self):
        provider_config = 'myprovider'
        expected = {
            'type': 'myprovider'
        }
        provider_config = xenos.load_provider_config(
            copy.deepcopy(provider_config))
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
        provider_config = xenos.load_provider_config(
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
        provider_config = xenos.load_provider_config(
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

        with self. assertRaisesRegex(
                EnosProviderMissingConfigurationKeys,
                r"\['missing-overriding1', 'missing-overriding2'\]"):
            xenos.load_provider_config(
                provider_config,
                default_provider_config)


@ddt.ddt
class TestPathLoading(unittest.TestCase):
    longMessage = True

    def setUp(self):
        self.sourcedir = C.ENOS_PATH
        self.workdir = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.workdir)

    def assertPathEqual(self, p1, p2, msg=None):
        self.assertEqual(os.path.normpath(p1),
                         os.path.normpath(p2),
                         msg)

    @ddt.data(('/abs/path/to/inventory.sample', 'inventory.sample'),
              ('/abs/path/to/workload/', 'workload/'))
    @ddt.unpack
    def test_seek_path(self, abspath, relpath):
        # Execution from the source directory
        with working_directory(self.sourcedir):
            self.assertPathEqual(xenos.seekpath(abspath),
                                 abspath,
                                 f"Seeking for an {abspath} defined "
                                 "with an absolute path should always "
                                 "return that path")

            self.assertPathEqual(xenos.seekpath(relpath),
                                 os.path.join(C.RSCS_DIR, relpath),
                                 f"Seeking for {relpath} from the source "
                                 "directory should seek into enos source")

        # Execution from a working directory
        with working_directory(self.workdir):
            self.assertPathEqual(xenos.seekpath(abspath),
                                 abspath,
                                 "Seeking for %s defined "
                                 "with an absolute path should always "
                                 "return that path" % abspath)

            self.assertPathEqual(xenos.seekpath(relpath),
                                 os.path.join(C.RSCS_DIR, relpath),
                                 "In absence of %s in the working "
                                 "directory, enos should seek for that one "
                                 "in sources" % relpath)

            # Build a fake `relpath` in the working directory and
            # check seekpath behaviour
            _path = pathlib.Path(relpath)
            _path.parent.is_dir() or _path.parent.mkdir()
            _path.exists() or os.mknod(str(_path))
            self.assertPathEqual(xenos.seekpath(relpath),
                                 os.path.join(self.workdir, relpath),
                                 "In presence of %s in the working directory,"
                                 "enos should take this one" % relpath)

    def test_seek_unexisting_path(self):
        unexisting = 'an/unexisting/path'

        with working_directory(self.sourcedir):
            with self.assertRaises(EnosFilePathError):
                xenos.seekpath(unexisting)

        with working_directory(self.workdir):
            with self.assertRaises(EnosFilePathError):
                xenos.seekpath(unexisting)


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
