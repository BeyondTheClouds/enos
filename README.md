# Enos

## Synopsis

This script deploys an OpenStack on Grid'5000 using
[Kolla](https://wiki.openstack.org/wiki/Kolla) and targets reproducible
experiments and allows easy :

* [deployment of the system](#providers)
* [customization of the system](#examples-of-customization)
* [benchmarking](#launch-a-workload)
* [visualization of various metrics](#post-mortem-analysis)

As mentionned before, Enos targets experiments with OpenStack. Enos isn't design
to deploy OpenStack in production.

## Providers

Enos is shipped with different providers that lets you deploy OpenStack on
various infrastructures. Core providers are :

* [Grid'5000](grid5000.fr/mediawiki/index.php/Grid5000:Home) (G5k)
* Virtualbox / [Vagrant](https://www.vagrantup.com/)  (Vbox)

Configuration may differ according to your choice.

## Installation

To install Enos, clone the repository :
<!--
```
pip install git+git://github.com/BeyondTheClouds/enos@master#egg=enos
```

## Contribute
-->
```
$ git clone https://github.com/BeyondTheClouds/enos
```

You should also choose to go with a virtualenv.

>  On Grid'5000, do the
following if virtualenv is missing:
```
$ pip install virtualenv --user # Install virtualenv
$ export PATH=~/.local/bin/:${PATH} # Put it into your path
```

Then install the dependencies:
```
$ cd enos
$ virtualenv venv
$ source venv/bin/activate
(venv)$ pip install -r requirements.txt
```

<!--
Finally, make sure to add ansible binaries to your PATH (export
PATH=YOUR_HOME/.local/bin:$PATH).

Finally, to launch the deployment, run:
```
python -m enos.enos deploy
```

And, to command line arguments:
```
python -m enos.enos -h
```

> Using a virtualenv is encouraged
-->

You can see the full options list supported by `Enos` with the following :

```
python -m enos.enos -h
```

## Configuration

To deploy a full stack, you need to provide a configuration file in the YAML
format. This file must include information about how OpenStack services must be deployed. `reservation.yaml.sample` is given as an
example.

```
# copy the sample file
$ cp reservation.yaml.sample reservation.yaml

#edit it with your parameters
$ <editor> reservation.yaml
```

> For G5k, nodes are grouped using the cluster names available on the
testbed


> For Vbox, nodes are grouped by size (tiny, small, medium, large).

## Note on Registry backends

**For G5k only.***

The deployment makes use of a private docker registry configured as a
mirror of the official docker registry. There are two modes
* `ceph: false`. It will start a fresh registry that will cache the
  images for the duration of the experiment.
* `ceph: true`. It will use an existing Ceph rados block device of the
  Rennes cluster.
The block device will be mounted and used as the registry storage.
Setting this is useful as the cache will persist different
experiments.

[The G5k ceph tutorial ](https://www.grid5000.fr/mediawiki/index.php/Ceph) will
guide you on how to create your rados block device.


## Deploying

Then, to launch the deployment:
```
(venv)$ python -m enos.enos deploy
```

> by default the script use the file `reservation.yaml` as configuration file

This will run the following phases:

* `up`: reserve physical machine on Grid'5000, deploys the base Linux
  distribution, instruments nodes with the monitoring stack, installs
  Kolla prerequisites (runtime dependencies, input files).

* `os`: launch the OpenStack deployment with Kolla

* `init`: bootstrap the freshly deployed OpenStack with users,
  images...


> Run `python -m enos.enos --help` for a full list of command-line arguments.

After the execution, the `./current` directory will contain some
generated files (please note that `current` is a symbolic link toward
the real directory associated to your deployment) and the results of
the benchmarks.


## Launch a workload

A workload is a set of scenarios grouped by type.
A workload is launched with the following command :

```
(venv)$ python -m enos.enos bench --workload=workload
```

enos will look into the `workload` directory for a file named
`run.yml`. This file is the description of the workload to launch.
One example is given below :

```
rally:
  enabled: true  # default is true
  args:
    concurrency:
      - 1
      - 2
      - 4
    times:
      - 1
  scenarios:
    - name: boot and list servers
      enabled: true # default is true
      file: nova-boot-list-cc.yml
      args:
        sla_max_avg_duration: 30
        times : 5
```

This will launch all the scenarios described under the scenarios keys with all
the possible parameters. The parameters are calculated using the cartesian
product of the parameters given under the args keys. Locally defined args
(scenario level) shadow globally defined args (top level). The same mechanism is
applied to the `enabled` values.  The scenario must be parameterized
accordingly. The key (rally here) defines the type of benchmark to launch : in
the future we may support other type of scenarios (Shaker, PerfkitBenchmarker
...)

After running the workload, a backup of the environment can be done through
`python -m enos.enos backup`.

## Post-mortem analysis

At the end of the benchmarks, various datas (logs, influxdb, rally home
directory, ...) are stored under the `current` directory. This enables
post-mortem analysis of the experimentation.

Please refer to the `result` directory to know how to get started with
*post-mortem* analysis


## Examples of customization

### Changing Kolla / Ansible variables

Custom Kolla / Ansible parameters can be put in the configuration file
under the key `kolla`.

### Changing the topology

Let's assume you want to run the `nova-conductor` in a dedicated node:

1) Add a new node reservation in the configuration file:

```yaml
paravance:
  control: 1
  network: 1
  compute: 1
  conductor-node: 1
```

2) Create an new inventory file in the `inventories` subdirectory
(copy paste the sample inventory) and change the group of the
conductor service:

```
[nova-conductor:children]
conductor-node
```

3) In the configuration file, points the inventory to use to this new
inventory.

4) Launch the deployment as usual, and you'll get the `nova-conductor`
on a dedicated node.

### Configuration tuning

At some point, Kolla default parameters won't fit your needs. Kolla
provides a mechanism to override custom section of configuration files
but isn't applicable in our case (at least in the corresponding
branch). So we implement a *quick and dirty* way of patching Kolla
code to enable custom configuration files to be used (and by extension
custom kolla code). See the possible patch declaration in
`ansible/group_vars/all.yml`. Patches should be added in the
configuration file of the experiment.

### Adding network constraints

Network constraints (latency/bandwidth limitations) are enabled by the use of groups of nodes. Resources *must* be described using a `topology` description instead of a `resources` description. An example of such a definition is given in the file `reservation.yaml.topology.sample`.

To enforce the constraints, you can invoke :
```
python -m enos.enos tc
```

> The machines must be available, thus the `up` phase must have been called before.

## Known limitations

* There might be an issue if your reservation contains multiple Grid'5000
  clusters composed of nodes that have different network device names, e.g.
  paravance that has `eth0` andl `eth1`, and parapluie that has devices `eth1`
  and `eth2`.

## Running the tests

```
pip install -r test-requirements
tox
```

## Why Enos?
https://en.wikipedia.org/wiki/Enos_(chimpanzee)


## License
Enos runs performance stress workloads on OpenStack for postmortem analysis.
Copyright (C) 2016 Didier Iscovery

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
