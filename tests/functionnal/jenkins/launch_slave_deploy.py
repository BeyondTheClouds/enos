#!/usr/bin/env python

from common import *
import logging
import os
from subprocess import call
import sys

def run_cmd(cmd):
    logging.info(cmd)
    call(cmd, shell=True)

if len(sys.argv) > 1:
    job_name = sys.argv[1]
else:
    job_name = 'enos-jenkins-deploy'

host, frontend = make_reservation(job_name=job_name,
                                  job_type='deploy')
logging.info("Deploying %s" % host)
deployed, undeployed = deploy(host)

if len(deployed) == 1:
    run_cmd("rsync -avz %s root@%s:/tmp/" % (JENKINS_FOLDER, host.address))
    # < /dev/null to prevent ssh to consume from stdin unexpectely
    run_cmd("ssh root@%s /tmp/jenkins/bootstrap.sh" % host.address)
    # Launch the slave using the current user
    # os.execl("/usr/bin/ssh", "ssh", "discovery@%s" % host.address,  "java -jar jenkins/slave.jar")
else:
    logging.error("Deployment failed")
    sys.exit(1)
