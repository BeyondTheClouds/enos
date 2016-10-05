# coding: utf-8
# -*- mode: ruby -*-
# vi: set ft=ruby :


# This Vagrantfile makes use of the plugin vagrant-g5k
# https://github.com/msimonin/vagrant-g5k
#
# version 0.0.13

# The list of experimentation. There will be one VM per
# experimentation. You can access it thought eg, `vagrant ssh idle`.
XPS =[
  {
    :name  => "idle",
    :confs => [ "cpt20-nfk05", "cpt20-nfk10", "cpt20-nfk25", "cpt20-nfk50" ]
  },
  {
    # dedicated 1 node  for each mariadb, haproxy, conductor, rabbitmq, memcached
    # with rally benchmark
    :name  => "load-ded",
    :confs => [ "cpt20-nfk05", "cpt20-nfk10", "cpt20-nfk25", "cpt20-nfk50-stopped"]
  },
  {
    # default topology
    # with rally benchmark
    :name  => "load-default",
    :confs => [ "cpt20-nfk05", "cpt20-nfk10", 'cpt20-nfk25']
  },
  {
    :name  => "concurrency",
    :confs => [ "ccy0001-0015-cpt20-nfk50",
                "ccy0025-0045-cpt20-nfk50",
                "ccy0100-1000-cpt20-nfk05" ]
  }
 # Add another experimentation
 # ,{ :name  => "vanilla",
 #    :confs => [ "cpt20-nfk05", "cpt20-nfk10", "cpt20-nfk25", "cpt20-nfk50" ]}
]

Vagrant.configure(2) do |config|
    # user to log with inside the vm
    config.ssh.username = "root"
    # password to use to log inside the vm
    config.ssh.private_key_path = File.join(ENV['HOME'], ".ssh/id_rsa_discovery")
 
    config.vm.provider "g5k" do |g5k|
      # The project id.
      # It is used to generate uniq remote storage for images
      # It must be uniq accros all project managed by vagrant.
      g5k.project_id = "vagrant-g5k"

      # user name used to connect to g5k
      g5k.username = "discovery"

      # private key
      g5k.private_key = File.join(ENV['HOME'], ".ssh/id_rsa_discovery")

      # site to use
      g5k.site = "rennes"
      g5k.gateway = "access.grid5000.fr"

      # walltime to use
      g5k.walltime = "03:00:00"

      # image location
      # g5k.image = {
      #  "path" => "$HOME/public/ubuntu1404.qcow2",
      #  "backing" => "copy"
      #}

      # it could be backed by the ceph
      g5k.image = {
        "pool"     => "discovery_kolla_registry",
        "rbd"      => "bases/alpine_docker",
        "id"       => "discovery",
        "conf"     => "/home/discovery/.ceph/config",
        "backing"  => "copy"
      }

      # ports to expose (at least ssh has to be forwarded)
      g5k.ports = ['2222-:22','3000-:3000', '8000-:80', '5601-:5601']
    end

    XPS.each do |xp|
      config.vm.define xp[:name] do |my|
        # box isn't used
        my.vm.box = "dummy"

        # From `boilerplate.yml`: this playbook relies on an `xps` variable.
        # The `xps` variable is a list that contains the name of all
        # experimentation. For instance, this list is as following for the
        # idle experimentation:
        # - idle-cpt20-nfk05
        # - idle-cpt20-nfk10
        # - idle-cpt20-nfk25
        # - idle-cpt20-nfk50
        #
        # This ruby method computes this list and gives it to
        # `ansible-playbook`. The construction of the list is based on the
        # name of the experimentation `xp[:name]` and the list of
        # experimentation done `xp[:confs]`
        xps = {:xps => xp[:confs].map { |cfg| xp[:name] + "-" + cfg } }

        # For the provision to run a dedicated proxy command seems necessary
        # in your ssh config (the provisionner seems to not take into account
        # the ssh-config of vagrant)
        # Host *.grid5000.fr
        #   User <login>
        #   StrictHostKeyChecking no
        #   ProxyCommand ssh <login>@194.254.60.4 "nc %h %p"
        my.vm.provision :ansible do |ansible|
          ansible.playbook = "boilerplate.yml"
          ansible.extra_vars = xps
#          ansible.verbose = "-vvvv"
        end
      end
    end
end
