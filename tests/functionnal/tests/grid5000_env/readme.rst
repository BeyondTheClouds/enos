Grid'5000 environment
---------------------

Workflow:

* Pull all the docker images on the slave
* Save the environment in ``/tmp/enos.tar.gz`` of the slave.


.. literalinclude:: ../../tests/functionnal/tests/grid5000_env/reservation.yaml
    :language: yaml
    :name: reservation.yaml
    :caption: Configuration
