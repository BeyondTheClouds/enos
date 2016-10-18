# -*- coding: utf-8 -
import os
from setuptools import setup, find_packages
from enos.utils.constants import VERSION


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='enos',
    author='discovery',
    author_email='discovery-dev@inria.fr',
    url='https://github.com/BeyondTheClouds/enos',
    description='This is Enos!',
    long_description=read('README.md'),
    version=VERSION,
    license='Apache-2.0',
    packages=find_packages(),
    install_requires=[
        'Jinja2==2.8',
        'execo==2.5.4',
        'ansible==2.1.2',
        'docopt==0.6.2',
        'requests==2.11.0',
        'httplib2==0.9.2',
        'python-dateutil==2.2',
        'python-glanceclient==2.3.0',
        'python-keystoneclient==3.4.0',
        'python-neutronclient==5.1.0',
        'python-novaclient==5.0.0',
        'python-openstackclient==2.6.0'
    ],
    entry_points={'console_scripts': ['enos = enos.enos:main']},
    include_package_data=True
)
