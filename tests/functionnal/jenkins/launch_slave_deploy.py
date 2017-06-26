#!/usr/bin/env python

from common import *
import os
import logging
from subprocess import call
import sys

if len(sys.argv) > 1:
    job_name = sys.argv[1]
else:
    job_name = 'enos-jenkins-deploy'

host, frontend = make_reservation(job_name=job_name,
                                  job_type='deploy')
logging.info("Deploying %s" % host)
deployed, undeployed = deploy(host)

if len(deployed) == 1:
  cmd = "rsync -avz %s root@%s:." % (JENKINS_FOLDER, host.address)
  logging.info(cmd)
  call(cmd, shell=True)
  os.execl("/usr/bin/ssh", "ssh", "root@%s" % host.address,  "java -jar jenkins/slave.jar")
else:
  logging.error("Deployment failed")
  sys.exit(1)
