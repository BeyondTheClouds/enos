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

Make sure to add ansible binaries to your PATH (export PATH=YOUR_HOME/.local/bin:$PATH).

## Configuration

To deploy a full stack, you need to provide a configuration file in the YAML format. This
file must include information about the Grid'5000 job and how the OpenStack services must
be deployed. `reservation.yaml.sample` is given as an example.

```
# copy the sample file
cp reservation.yaml.sample reservation.yaml

#edit it with your parameters
<editor> reservation.yaml
```

## Running
Then, to run launch the deployment, run:
```
./01_deploy_nodes.py
```

> by default the script use the file `reservation.yaml` as configuration file

On the first run, the script will create an OAR Grid job with a specific name. On subsequent
runs, it will find the running job and use it. The job name can be specified in the YAML
configuration file.

Run `./01_deploy_nodes.py -h` for a full list of command-line arguments.

After the execution, the `./current` directory will contain some generated
files (please note that `current` is a symbolic link toward the real directory
associated to your deployment)  

## Limitations

* The network interfaces inserted in the `templates/globals.yml.jinja2` file are taken from the
Grid'5000 API for the first cluster specified in the YAML file.
This may be a problem if you reservation contains multiple Grid'5000 clusters composed of nodes that
have different network device names, e.g. paravance that has `eth0` andl `eth1`, and parapluie that
has devices `eth1` and `eth2`.

## Registry backends

The deployment makes use of a private docker registry configured as a mirror of the official docker registry.
There are two modes :

* `ceph: false`. It will start a fresh registry that will cache the images for the duration of the experiment
* `ceph: true`. It will use an existing Ceph rados block device of the Rennes cluster.
The block device will be mounted and used as the registry storage. Setting this is usefull as the cache will persist different experiments.

[The G5k ceph tutorial ](https://www.grid5000.fr/mediawiki/index.php/Ceph) will guid you on how to create your rados block device.



## License
This code is released under the GNU General Public License.

## Contributors

* [Anthony Simonet](http://www.anthony-simonet.fr)
* [Matthieu Simonin](http://people.irisa.fr/Matthieu.Simonin)
