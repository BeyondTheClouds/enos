# Kolla-G5K
## Synopsis
This script deploys an OpenStack on Grid'5000 using [Kolla](https://wiki.openstack.org/wiki/Kolla),
isolating some services on different nodes. Everything must be configured in a single JSON file
and then the deployment can be run in one command.

## Requirements
Kolla-G5K-Multinode requires pip, [Execo](http://execo.gforge.inria.fr/) and [Jinja](http://jinja.pocoo.org/).

## Installation

To install Kolla-G5K-Multinode, first clone the repository:
```
https://github.com/BeyondTheClouds/kolla-g5k
```

Then install the dependencies:
```
cd kolla_g5k
pip install -r requirements.txt --user
```

Make sure to add ansible binaries to your PATH.

## Configuration
To deploy a full stack, you need to provide a configuration file in the YAML format. This
file must include information about the Grid'5000 job and how the OpenStack services must
be deployed. `reservation.yml` is given as an example.

You also need to provide credentials to a Ceph cluster for the Docker registry. Just place you
`.ceph` directory in `roles/registry/files/`:
```
$ ls -l ~/.ceph
total 8
-rw-r--r-- 1 you users 68 Aug  3 14:58 ceph.client.discovery.keyring
-rw-r--r-- 1 you users 91 Aug  3 14:59 config
$ cp -r ~/.ceph roles/registry/files/
```

## Running
Then, to run launch the deployment, run:
```
./deploy.py -f reservation.yml
```

On the first run, the script will create an OAR Grid job with a specific name. On subsequent
runs, it will find the running job and use it. The job name can be specified in the YAML
configuration file.

Run `./deploy.py -h` for a full list of command-line arguments.

After the execution, a new directory will contain some generated files.

## Limitations

* The network interfaces inserted in the `templates/globals.yml.jinja2` file are taken from the
Grid'5000 API for the first cluster specified in the YAML file.
This may be a problem if you reservation contains multiple Grid'5000 clusters composed of nodes that
have different network device names, e.g. paravance that has `eth0` andl `eth1`, and parapluie that
has devices `eth1` and `eth2`.

## License
This code is released under the GNU General Public License. It is also worth
mentionning here that it is being developped by [me](http://www.anthony-simonet.fr)
as part of my work at [Inria](http://www.inria.fr).
