Packaging
---------

Workflow:

* Deploys OpenStack in a standalone mode using the Static provider in a vagrant
  box. 
* Check if a server can be booted and if Rally can be launched.
* Destroy the deployment (leave the images)
* Package the box


.. literalinclude:: ../../tests/functionnal/tests/packaging/reservation.yaml
    :language: yaml
    :name: reservation.yaml
    :caption: Configuration
