# Kolla-G5K-Multinode
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

## Running
To deploy a full stack, you need to provide a configuration file in the JSON format. This
file must include information about the Grid'5000 job and how the OpenStack services must
be deployed. `reservation.json` is given as an example.

Then, to run launch the deployment, run:
```
./deploy.py -f reservation.json
```

On the first run, the script will create an OAR Grid job with a specific name. On subsequent
runs, it will find the running job and use it. The job name can be specified in the JSON
configuration file.

Run `./deploy.py -h` for a full list of command-line arguments.

After the execution, a new directory will contain some generated files.


## Limitations

* The network interfaces are specified in the ``` templates/globals.yml.jinja2``` file.
 The mapping isn't generated (yet), an may vary according to the nodes of your reservation.

## License
This code is released under the GNU General Public License. It is also worth
mentionning here that it is being developped by [me](http://www.anthony-simonet.fr)
as part of my work at [Inria](http://www.inria.fr).
