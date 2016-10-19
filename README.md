# Kolla-G5K

## Synopsis
This script deploys an OpenStack on Grid'5000 using
[Kolla](https://wiki.openstack.org/wiki/Kolla) and allows easy customization of the system (change in the default topology, configuration parameters) and reproductible experiments.

## Installation
To install Kolla-G5K, first connect to the Grid'5000 frontend of your choice :
and clone the repository

```
git clone https://github.com/BeyondTheClouds/kolla-g5k
```

Then install the dependencies:

```
cd kolla-g5k
pip install -r requirements.txt --user
```
Make sure to add ansible binaries to your PATH (export
PATH=YOUR_HOME/.local/bin:$PATH).

> Using a virtualenv is encouraged

## Configuration

To deploy a full stack, you need to provide a configuration file in the YAML
format. This file must include information about the Grid'5000 job and how the
OpenStack services must be deployed. `reservation.yaml.sample` is given as an
example.

```
# copy the sample file
cp reservation.yaml.sample reservation.yaml

#edit it with your parameters
<editor> reservation.yaml
```

## Note on Registry backends

The deployment makes use of a private docker registry configured as a mirror of
the official docker registry.  There are two modes :

* `ceph: false`. It will start a fresh registry that will cache the images for
  the duration of the experiment
* `ceph: true`. It will use an existing Ceph rados block device of the Rennes
  cluster.
The block device will be mounted and used as the registry storage. Setting this
is usefull as the cache will persist different experiments.

[The G5k ceph tutorial ](https://www.grid5000.fr/mediawiki/index.php/Ceph) will
guide you on how to create your rados block device.


## Deploying

Then, to launch the deployment :
```
./kolla-g5k.py
```

> by default the script use the file `reservation.yaml` as configuration file

This will run all the following phases :

* `prepare-node` : reserve physical machine on Grid'5000, deploys the base
linux distribution, instruments nodes with the monitoring stack, installs Kolla
prerequisites (runtime dependencies, input files.

* `install-os` : launch the Kolla deployment

* `init-os` : bootstrap the freshly deployed OpenStack with users, images...


> Run `./kolla-g5k.py --help` for a full list of command-line arguments.

After the execution, the `./current` directory will contain some generated
files (please note that `current` is a symbolic link toward the real directory
associated to your deployment)  and the results of the benchmarks


## Launch rally benchmarks

You can launch a rally benchmark using :

```
./kolla-g5k.py --scenarios=<scenario file>
```

Ansible will connect to the node(s) hosting Rally service and launch in sequence
all the benchmarks described in the scenario file.

> The scenario file must resides in the rally subdirectory


## Post-mortem analysis

At the end of the benchmarks, various datas (logs, influxdb, rally home
directory, ...) are stored under the `current` directory. This enables
post-mortem analysis of the experimentation.

Please refer to the `result` directory to know how to get started with
*post-mortem* analysis


## Example of customizations

### Changing Kolla / Ansible variables

Custom Kolla / Ansible parameters can be put in the configuration file under the
 key `kolla`.

### Changing the topology

Let's assume you want to run the `nova-conductor` in a dedicated node :

1) Add a new node reservation in the configuration file :

```yaml
paravance:
  control: 1
  network: 1
  compute: 1
  conductor-node: 1
```

2) Create an new inventory file in the `inventories` subdirectory
(copy paste the sample inventory) and change the group of the conductor service :


### Configuration tuning

At some point, Kolla default parameters won't fit your needs. Kolla provides a
mechanism to override custom section of configuration files but isn't applicable
in our case (at least in the corresponding branch). So we implement a *quick and dirty*
way of patching Kolla code to enable custom configuration files to be used
(and by extension custom kolla code).
See the possible patch declaration in `ansible/group_vars/all.yml`. Patches should be added in the configuration file of the experiment.

```
[nova-conductor:children]
conductor-node
```

3) In the configuration file, points the inventory to use to this new inventory.

4) Launch the deployment as usual, and you'll get the `nova-conductor` on a
dedicated node.

## Known limitations

* There might be an issue if your reservation contains multiple Grid'5000
  clusters composed of nodes that have different network device names, e.g.
  paravance that has `eth0` andl `eth1`, and parapluie that has devices `eth1`
  and `eth2`.


## License
This code is released under the GNU General Public License.
