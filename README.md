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
https://github.com/asimonet/kolla_g5k_multinodes
```

Then install the dependencies:
```
cd kolla_g5k_multinodes
pip install -r requirements.txt
```

## Running
To deploy a full stack, you need to provide a configuration file in the JSON format. This
file must include information about the Grid'5000 job and how the OpenStack services must
be deployed. `reservation.json` is given as an example.

Then, to run launch the deployment, run:
```
./deploy.py -f reservation.json
```

Run `./deploy.py -h` for a full list of command-line arguments.

After the execution, a new directory will contain some generated files.

## License
This code is released under the GNU General Public License. It is also worth
mentionning here that it is being developped by [me](http://www.anthony-simonet.fr)
as part of my work at [Inria](http://www.inria.fr).
