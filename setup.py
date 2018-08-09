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
        'enoslib',
        'influxdb==4.0.0',
        'docopt>=0.6.2,<0.7.0',
        'httplib2==0.9.2',
        # - ReadTheDocs
        'GitPython>=2.1.5',
    ],
    extras_require={
        'openstack': [
            'python-openstackclient',
            'python-neutronclient',
            'python-blazarclient>=1.1.1'
        ]
    },
    entry_points={'console_scripts': ['enos = enos.cli:main']},
    include_package_data=True
)
