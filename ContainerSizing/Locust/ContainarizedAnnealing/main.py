from kubernetes import client, config
import random
import gevent
from greenlet import greenlet
import time
import os
import numpy as np
import requests
import signal
import sys
import requests
import argparse
import logging


# Configure the logging settings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Log some messages
# logging.info('This is an informational message.')
# logging.warning('This is a warning message.')
# logging.error('This is an error message.')

# Example usage: Update resources for a deployment named 'my-deployment' in the 'default' namespace
# update_deployment_resources("locust-master", "default", "500m", "512Mi", "1", "1Gi")
def update_deployment_resources(deployment_name, namespace, cpu_request, memory_request, cpu_limit, memory_limit):
    # Load the in-cluster Kubernetes configuration
    config.load_incluster_config()

    # Create an instance of the Kubernetes API client
    api = client.AppsV1Api()

    # Retrieve the deployment object
    deployment = api.read_namespaced_deployment(deployment_name, namespace)

    # Update the resource requests and limits in all containers of the deployment
    for container in deployment.spec.template.spec.containers:
        container.resources.requests = {
            'cpu': cpu_request,
            'memory': memory_request
        }
        container.resources.limits = {
            'cpu': cpu_limit,
            'memory': memory_limit
        }

    # Update the deployment
    api.patch_namespaced_deployment(deployment_name, namespace, deployment)

    print(f"Updated resources for deployment '{deployment_name}' in namespace '{namespace}'")
def patch_deployment(deployment_name, cores, mem):
    update_deployment_resources(deployment_name, "default", cores, mem, cores, mem)

def get_stats():
    global LOCUST_URL
    LOCUST_STATS_URL = "{}/stats/requests".format(LOCUST_URL)
    response = requests.get(LOCUST_STATS_URL).json()
    stats = response['stats']
    return stats

def objective_function(exec_time, cores, mem):
    return exec_time + cores/TOTAL_CORES + mem/TOTAL_MEM
def annealing_probability(y1, y2, tau):
    return np.exp((-max(y2-y1,0))/tau)
def explore_configuration():
    global CONFIGURATIONS
    # pick random micro
    # exploree config for both mem and core
    _random_micro = random.choice(CONFIGURATIONS)
    _index_micro  = CONFIGURATIONS.index(_random_micro)
    old_cores = _random_micro[1]
    old_mem   = _random_micro[2]
    
    # Checking boundary cases
    new_cores = old_cores + (STEP_SIZE if random.random() > 0.5 else (-STEP_SIZE))
    if new_cores > max(POSSIBLE_CORES):
        new_cores = max(POSSIBLE_CORES)
    elif new_cores < min(POSSIBLE_CORES):
        new_cores = min(POSSIBLE_CORES)

    new_mem = old_mem + (STEP_SIZE if random.random() > 0.5 else (-STEP_SIZE))
    if new_mem > max(POSSIBLE_MEMS):
        new_mem = max(POSSIBLE_MEMS)
    elif new_mem < min(POSSIBLE_MEMS):
        new_mem = min(POSSIBLE_MEMS)

    
    return _index_micro, (_random_micro[0], new_cores, new_mem)
def patch_all_deployments():
    global CONFIGURATIONS
    for deployment_name, core, mem in CONFIGURATIONS:
        update_deployment_resources(deployment_name, "default", "{}m".format(core), "{}Mi".format(mem), "{}m".format(core), "{}Mi".format(mem))



if __name__ == '__main__':

    

    # argument parsers
    parser = argparse.ArgumentParser(description='Annealing processor')
    parser.add_argument("LOCUST_URL", help="url of Locust master")
    parser.add_argument("-t", "--tau", type=int, default=10, help="set annealing temprature (default: 10)")
    parser.add_argument("-p", "--period", type=int, default=300, help="epoch duration")
    # parser.add_argument("--tau", )
    args = parser.parse_args()

    cell_count = 0


    # ------------------
    # ANNEALING PARAMS
    # ------------------
    TAU = args.tau
    #TODO: GET THE LEST OF DEPLOYMENTS FROM SOMEWHERE ELSE INSTED OF HARDCODING
    DEPLOYMENTS = [
    "compose-post-service", 
    "home-timeline-redis", 
    "home-timeline-service",
    "jaeger",
    "media-frontend",
    "media-memcached",
    "media-mongodb",
    "media-service",
    "post-storage-memcached",
    "post-storage-mongodb",
    "post-storage-service",
    "social-graph-mongodb",
    "social-graph-redis",
    "social-graph-service", 
    "text-service",
    "unique-id-service",   
    "url-shorten-memcached",
    "url-shorten-mongodb",
    "url-shorten-service",
    "user-memcached",
    "user-mention-service",
    "user-mongodb",
    "user-service",
    "user-timeline-mongodb",
    "user-timeline-redis",
    "user-timeline-service",
    "nginx-thrift",
    ]

    CONFIGURATIONS = [(i, 1000, 1000) for i in DEPLOYMENTS]

    NUMBER_OF_MICROSERVICES = 27
    TOTAL_CORES = 1500 * NUMBER_OF_MICROSERVICES
    TOTAL_MEM   = 1500 * NUMBER_OF_MICROSERVICES
    STEP_SIZE = 100
    POSSIBLE_CORES = [i for i in range(100, 1501, STEP_SIZE)]
    POSSIBLE_MEMS  = [i for i in range(100, 1501, STEP_SIZE)]
    PERIOD = args.period
    LOCUST_URL = args.LOCUST_URL

    # --------------------
    #       Greenlets
    # --------------------
    annealing_greenlet = None
    old_objective = None

    def signal_handler(sig, frame):
        # Perform cleanup or trigger necessary actions
        sys.exit(0)

    # Register the signal handler
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logging.info("signal handlers registerd")


    logging.info("pathcing all deployemnts wiht init config")
    patch_all_deployments()
    logging.info("done pathcing with init config")
    time.sleep(PERIOD)
    while True:
        #exec_time = environment.runner.stats.total.median_response_time
        exec_time = int(get_stats()[-1]['ninety_ninth_response_time'])
        if old_objective is None:
            logging.info("performing annealing for the first time")
            old_objective = objective_function(exec_time, sum([i[2] for i in CONFIGURATIONS]), sum([i[2] for i in CONFIGURATIONS]))
        else:
            logging.info("performing annealing")
            index_micro, new_config = explore_configuration()
            _configs = CONFIGURATIONS.copy()
            _configs[index_micro] = new_config
            patch_deployment(new_config[0], new_config[1], new_config[2])
            new_objective = objective_function(exec_time, sum([i[1] for i in _configs]), sum([i[2] for i in _configs]))
            if cell_count < 5000:
                logging.info('datapoint,{},{}'.format(cell_count, new_objective))
                cell_count += 1
            if random.random() < annealing_probability(old_objective, new_objective, TAU):
                old_objective = new_objective
                CONFIGURATIONS = _configs
                logging.info("accepted config: ".format(new_config))
            else:
                logging.info("rejected config: ".format(new_config))
        time.sleep(PERIOD)












