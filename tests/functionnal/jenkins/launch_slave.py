#!/usr/bin/env python

from common import *
import logging
import os
from subprocess import call
import sys

if len(sys.argv) > 1:
    job_name = sys.argv[1]
else:
    job_name = 'enos-jenkins'

host, frontend = make_reservation(job_name=job_name)
# propagating the jenkins folder to the targetted site
cmd = "rsync -avz %s %s:." % (JENKINS_FOLDER, frontend)
logging.info(cmd)
call(cmd, shell=True)
os.execl("/usr/bin/ssh", "ssh", host.address,  "java -jar jenkins/slave.jar")
