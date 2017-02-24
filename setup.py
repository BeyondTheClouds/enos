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
    license='GPL-3.0',
    packages=find_packages(),
    install_requires=[
        'Jinja2==2.9',
        'execo==2.6.1',
        'ansible==2.1.2',
        'influxdb==4.0.0',
        'docopt==0.6.2',
        'httplib2==0.9.2',
        'python-dateutil==2.2',
        'python-neutronclient==6.1.0',
        'python-openstackclient>=3.0.0,<=4.0.0',
        'python-vagrant==0.5.14'
    ],
    entry_points={'console_scripts': ['enos = enos.enos:main']},
    include_package_data=True
)
