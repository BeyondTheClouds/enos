## On Jenkins

Configure jenkins node to use it:
e.g: `ssh  -o StrictHostKeyChecking=no discovery@access.grid5000.fr "ssh luxembourg -o ConnectTimeout=600 jenkins/launch_slave_deploy.py <job_name>"`

## On g5k frontend

Install those scripts alongside the slave.jar file to use.
You can get the slave.jar file from jenkins GUI.

## Existing jobs

* `enos-functionnal`:
Wrapper to the following jobs. Triggered via a webhook on the push events on github.

* `enos-vagrant-vbox`:
Test the vagrant provisioner on a multinode vagrant/vbox setup.

* `enos-vagrant-packaging`:
Test the static provider and package the resulting box in a usable vagrant/vbox box.

* `enos-vagrant-topology`:
Test the network emulation on a multinode vagrant/vbox setup.

* `enos-g5k`
Test the g5k provider in an allinone deployment.

## Misc.

Each job is bound to a specific slave on G5K. If the slave is already created it
could be reused (until the walltime expires - default to 02:00:00).

Each job is scripted and the entry point for jenkins is `jenkins.sh`.
