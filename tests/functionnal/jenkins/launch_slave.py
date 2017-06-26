#!/usr/bin/env python

from common import *
import os
import logging
from subprocess import call

host, frontend = make_reservation()
# propagating the jenkins folder to the targetted site
cmd = "rsync -avz %s %s:." % (JENKINS_FOLDER, frontend)
logging.info(cmd)
call(cmd, shell=True)
os.execl("/usr/bin/ssh", "ssh", host.address,  "java -jar jenkins/slave.jar")
