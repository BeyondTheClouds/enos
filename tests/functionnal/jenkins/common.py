#!/usr/bin/env python

import execo as ex
import execo_g5k as ex5
import time
from execo.time_utils import *
from execo.process import *
import logging
import random

WALLTIME = "02:00:00"
JENKINS_FOLDER = "~/jenkins"
JOB_NAME="discovery-jenkins-test"
ENV_NAME="debian9-x64-big"
#CLUSTERS=["parasilo", "paravance", "parapluie"]
#exclu = ex5.api_utils.get_g5k_clusters()
# list that contains all clusters excepts those in okay list
#excluded = [c for c in exclu if c not in CLUSTERS]
# Don't exclude anything for now
excluded = ["sagittaire"]


logging.basicConfig(level=logging.DEBUG)
def retry(func):

    def wrapper(*args, **kwargs):
        retries = 3
        while retries > 0:
            try:
                return func(*args, **kwargs)
            except:
                logging.info("Error ... retrying")
                retries = retries - 1
        return func(*args, **kwargs)

    return wrapper

@retry
def make_reservation(job_name=JOB_NAME, job_type='allow_classic_ssh'):
    plan = ex5.planning
    end = ex.time_utils.format_date(time.time()+12600)

    logging.basicConfig(level=logging.DEBUG)
    oargrid_job_id, _ = ex5.planning.get_job_by_name(job_name)
    if oargrid_job_id is None:
        logging.info("Starting a new job")
        planning = plan.get_planning(endtime=end)
        slots = plan.compute_slots(planning, walltime=WALLTIME, excluded_elements=excluded)
        startdate, enddate, resources = plan.find_free_slot(slots, {'grid5000':1})
        logging.info("startdate = %s, enddate = %s resources = %s" % (startdate, enddate, resources))
        resources = plan.distribute_hosts(resources, {'grid5000':1}, excluded_elements=excluded)
        # shuffling to load balance load accros nodes
        random.shuffle(resources)
        specs = plan.get_jobs_specs(resources, excluded_elements=excluded)
        spec, frontend = specs[0]
        spec.name = job_name
        logging.info("specs = %s" % spec)
        oargrid_job_id, _ = ex5.oargridsub(specs, job_type=job_type, walltime=WALLTIME)

    logging.info("Using running oargrid job %s" % oargrid_job_id)

    jobs = ex5.oargrid.get_oargrid_job_oar_jobs(oargrid_job_id=oargrid_job_id)
    # Get the frontend
    _, frontend = jobs[0]
    # Get the host
    hosts = ex5.get_oargrid_job_nodes(oargrid_job_id)
    logging.info("The slave will be running on %s,%s" % (hosts[0], frontend))
    return hosts[0], frontend

def deploy(host):
    return ex5.deploy(ex5.Deployment([host], env_name=ENV_NAME))
