# Post-Mortem analysis

## What's inside the VMs ?

Each virtual machine (VM) offer a toolbox to analyse various datas from the experimentation made with kolla-g5k. The datas themselves are also located inside the VM during the creation of the VM.

You'll find :

* Nginx exposed on port 8000. It allows you to browse Rally reports, confs and logs.
* Grafana exposed on port 3000. It gives access of all the metrics collected during the experimentation
* Kibana exposed on port 5601. It let you explores the logs.


## List of provided experimentation

* idle : *todo wiki url*
* load-ded : *todo wiki url*
* load-default : *todo wiki url*
* concurrency : *todo wiki url*

## Accessing the results

Start a specific virtual machine :

```
vagrant up <experimentation>
```

Shutdown the virtual machine
```
vagrant halt <experimentation>
```

## Creating new results

*todo*

## Known limitation

* The current implementation is tight to Grid'5000.
* When creating a new set of result, indexing all the logs in elasticsearch will take some time.
* From time to time VMs root filesystem goes read-only. Manually fsck the root partition and reboot may solve the issue `fsck /dev/vg0/lv_root`.
