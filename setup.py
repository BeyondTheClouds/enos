# -*- coding: utf-8 -
import os
from setuptools import setup, find_packages
from enos.utils.constants import VERSION


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='enos',
    version=VERSION,
    description='Experimental eNvironment for OpenStack',
    url='https://github.com/BeyondTheClouds/enos',
    author='discovery',
    author_email='discovery-dev@inria.fr',
    license='GPL-3.0',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        ],
    keywords='OpenStack, Evaluation, Reproducible Research, '
             'Grid5000, Chameleon, Vagrant, Virtualbox',
    long_description=read('README.rst'),
    packages=find_packages(),
    install_requires=[
        'Jinja2==2.9',
        'execo==2.6.1',
        'ansible>=2.3.0,<2.4.0',
        'influxdb==4.0.0',
        'docopt>=0.6.2,<0.7.0',
        'httplib2==0.9.2',
        'python-dateutil>=2.2',
        'python-openstackclient>=3.0.0,<=4.0.0',
        'python-vagrant>=0.5.14,<0.6.0',
        # - Chameleon
        # NOTE(msimonin): chameleon provider is using
        # a deprecated API (add_floating_ip).
        'python-novaclient<10',
        'python-blazarclient==1.0.1',
        'python-neutronclient==6.3.0',
        # - ReadTheDocs
        'GitPython>=2.1.5'
    ],
    entry_points={'console_scripts': ['enos = enos.enos:main']},
    include_package_data=True
)
