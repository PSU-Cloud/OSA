from kubernetes import client, config
import time
import os
import random
import logging
import numpy as np
import json
import re

root_logger= logging.getLogger()
root_logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('exprt.log', 'w', 'utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(name)s:%(levelname)s:%(message)s'))
root_logger.addHandler(handler)


SOCIAL_DEPLOYMENTS = [
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


HOTEL_DEPLOYMENTS = [
"consul-hotel-hotelres",                                          
"frontend-hotel-hotelres",                                        
"geo-hotel-hotelres",                                             
"jaeger-hotel-hotelres",                                          
"memcached-profile-1-hotel-hotelres",                             
"memcached-rate-1-hotel-hotelres",                                
"memcached-reserve-1-hotel-hotelres",                            
"mongodb-geo-hotel-hotelres",                                       
"mongodb-profile-hotel-hotelres",                                   
"mongodb-rate-hotel-hotelres",                                      
"mongodb-recommendation-hotel-hotelres",                            
"mongodb-reservation-hotel-hotelres",                               
"mongodb-user-hotel-hotelres",                                      
"profile-hotel-hotelres",                                           
"rate-hotel-hotelres",                                              
"recommendation-hotel-hotelres",                                    
"reservation-hotel-hotelres",                                       
"search-hotel-hotelres",                                            
"user-hotel-hotelres",
]

MEDIA_DEPLOYMENTS = [
"cast-info-memcached",     
"cast-info-mongodb",       
"cast-info-service",       
"compose-review-memcached",
"compose-review-service",  
"jaeger",                
"movie-id-memcached",      
"movie-id-mongodb",        
"movie-id-service",        
"movie-info-memcached",    
"movie-info-mongodb",      
"movie-info-service",     
"movie-review-mongodb",    
"movie-review-redis",      
"movie-review-service",    
"nginx-web-server",        
"page-service",            
"plot-memcached",          
"plot-mongodb",            
"plot-service",            
"rating-redis",            
"rating-service",          
"review-storage-memcached",
"review-storage-mongodb",  
"review-storage-service",  
"text-service",            
"unique-id-service",       
"user-memcached",          
"user-mongodb",            
"user-review-mongodb",     
"user-review-redis",       
"user-review-service",     
"user-service",            
]


# SETUP PARAMS
# Specify your workload path
WORKLOAD_PATH = "<INSERT WORKLOAD PATH HERE>"
# Specify your wrk2 API address for the microservice
API_ADDRS = "<INSERT WRK2 API ADDRESS FOR DEATHSTARBENCH>"




## ANNEALING AND MICROSERVICES PARAMS
#XXX: select the deployment to use for expirementation
CONFIGURATIONS = [(i, 100, 100) for i in SOCIAL_DEPLOYMENTS]
# CONFIGURATIONS = [(i, 100, 100) for i in HOTEL_DEPLOYMENTS]
# CONFIGURATIONS = [(i, 100, 100) for i in MEDIA_DEPLOYMENTS]

NUMBER_OF_MICROSERVICES = len(CONFIGURATIONS)
TOTAL_CORES = 1500 * NUMBER_OF_MICROSERVICES
TOTAL_MEM   = 1500 * NUMBER_OF_MICROSERVICES
STEP_SIZE = 100
POSSIBLE_CORES = [i for i in range(100, 1501, STEP_SIZE)]
POSSIBLE_MEMS  = [i for i in range(100, 1501, STEP_SIZE)]

KUBER_HOST = "<INSERT KUBERNETES HOST HERE>"
# Define the bearer token we are going to use to authenticate.
# See here to create the token:
# https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/
KUBE_TOKEN = "<INSERT KUBERNETES TOKEN HERE>"
MICRO_HOST = "<INSERT MICROSERVICE HOST HERE>"

## EXPIREMENTAL PARAMS
NUM_EPOCHS = 2
EPOCH_DURATION = 60 # seconds
NUM_THREADS = 10
NUM_CONN = 100
REQ_RATE = 250

# Annealing Params
TAU = 10

# parses the output of wrk2 script
# returns a dict with the following keys
# mean, std, max, total_count, cdf
def parse_wrk2(filename):
    '''
    parses a single output of the wrk2 script
    param: filename - name of a file containing the output
    output: dict()
    '''
    mean = None
    stdDev = None
    max  = None
    total_count = None

    with open(filename, 'r') as fd:
        lines = fd.read().splitlines()
        for line in lines:
            if '#[Mean' in line:
                mean = float(line.strip('\n').split(',')[0].split('=')[1])
                stdDev  = float(line.strip('\n').split(',')[1].split('=')[1].strip(']'))
            elif '#[Max' in line:
                max = float(line.strip('\n').split(',')[0].split('=')[1])
                total_count = int(line.strip('\n').split(',')[1].split('=')[1].strip(']'))

        for index, line in enumerate(lines):
            if 'Detailed Percentile spectrum:' in line:
                break
        _top = lines[index+3:]

        data = None
        for index, line in enumerate(reversed(_top)):
            if '#[Mean' in line:
                data = list(reversed(list(reversed(_top))[index+1:]))
                break
        
        # value, percentile, total, 1/(1-percentile)
        cdf = []
        for point in data:
            _point = re.sub("\s+", ",", point.strip())
            cdf.append([float(i) for i in _point.split(',')])
  
    res = {
        'mean' : mean,
        'std'  : stdDev,
        'max'  : max,
        'total_count' : total_count,
        'cdf' : cdf,
    } 

    return res

# returns the objective value
# XXX: you can define however you like the objective of your annealing process
def objective_function(exec_time, cores, mem):
    return exec_time + cores/TOTAL_CORES + mem/TOTAL_MEM

# returns a probability of accepting the new configuration
def annealing_probability(y1, y2, tau):
    return np.exp((-max(y2-y1,0))/tau)

# returns a tuple of (index of microservice, new configuration)
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

    
# uses ssh to patch the deployment (no need for token from kubernetes)  
#  XXX: this is a hack, we should use kubernetes api to patch the deployment  
def patch_deployment(dep, core, mem):
    #XXX: replace node1 with the name of kubernetes node
    os.system("ssh node1 'kubectl set resources deployment {} --limits=cpu={}m,memory={}Mi --requests=cpu={}m,memory={}Mi'".format(dep,core,mem,core,mem))

# uses kubernetes api to patch the deployment
def patch_all_deployments(v1):
    global CONFIGURATIONS
    logging.debug("patching all deployments")
    for config in CONFIGURATIONS:
        patch_deployment(config[0], config[1],config[2])
    logging.debug("done patching all deployments, running workload for first objective")

    is_cluster_ready(v1)    

# wait until all pods are ready
# XXX: this is a hack, we should use kubernetes api to check if all pods are ready
def is_cluster_ready(v1):
    # wait for all pods to be ready from the deployment
    NUMBER_OF_PODS = len(CONFIGURATIONS)
    retry = True 
    # print("Listing pods with their IPs:")
    while retry == True:
        ret = v1.list_pod_for_all_namespaces(watch=False)
        pods = []
        for i in ret.items:
            if i.metadata.namespace == 'default':
                pods.append(i)
        if len(pods) == NUMBER_OF_PODS:
            retry = False
        else:
            print("waiting..", len(pods))
            time.sleep(1)


#TODO: logger for results
def myLogger(data_point):
    results = json.load(open("result.json", "r"))
    results.append(data_point)
    json.dump(results, open("result.json", "w"), indent=4)


def run_workload(configs, v1):
    CMD = "../wrk2/wrk -D exp -t {} -c {} -d {} -L -s ".format(NUM_THREADS, NUM_CONN,EPOCH_DURATION)

    # Compose post
    _WORKLOAD_PATH = WORKLOAD_PATH
    _API_ADDRS = API_ADDRS +" "

    REQ_RATE_ARG = "-R {} ".format(REQ_RATE)
    CMD_STATEMENT = CMD + _WORKLOAD_PATH + _API_ADDRS + REQ_RATE_ARG + "> current_config.txt"
    print("running: " + CMD_STATEMENT)
    os.system(CMD_STATEMENT)

    # save the current config to a file
    os.system("echo '#####' >> all_configs.txt")
    os.system("cat current_config.txt >> all_configs.txt")

    res = parse_wrk2('current_config.txt')

    ## get the locations of each microservice
    # for debug/logging purposes
    ret = v1.list_pod_for_all_namespaces(watch=False)

    # get the node name for each microservice
    configs_with_node =[]
    for config in configs:
        pod_name = config[0]
        _new_config_with_node = None
        for i in ret.items:
            if i.metadata.namespace == "default" and pod_name in i.metadata.name:
                _new_config_with_node = (config[0], config[1], config[2], i.spec.node_name)
                break
        assert(_new_config_with_node != None)
        configs_with_node.append(_new_config_with_node)
        
    _configs = []
    for c in configs_with_node:
        _c = {
            "name": c[0],
            "cores": c[1],
            "mem": c[2],
            "node": c[3]
        }
        _configs.append(_c)

    data_point = {
        "configs" : _configs,
        "perf" : res
    }

    myLogger(data_point)
    return res['mean']


def main():    
    global CONFIGURATIONS

    aToken = KUBE_TOKEN
    # Create a configuration object
    aConfiguration = client.Configuration()
    # Specify the endpoint of your Kube cluster
    aConfiguration.host = KUBER_HOST
    aConfiguration.verify_ssl = False
    aConfiguration.api_key = {"authorization": "Bearer " + aToken}
    # Create a ApiClient with our config
    aApiClient = client.ApiClient(aConfiguration)

    # Do calls
    v1 = client.CoreV1Api(aApiClient)
    
    # 1. get initial objective using initial config
    patch_all_deployments(v1)
    exec_time = run_workload(CONFIGURATIONS, v1)
    old_objective = objective_function(exec_time, sum([i[2] for i in CONFIGURATIONS]), sum([i[2] for i in CONFIGURATIONS]))
    logging.debug("workload done with mean time {}ms, objective value {}".format(exec_time, old_objective)) 
    logging.debug("doing {} iterations, with temp tau={}".format(NUM_EPOCHS, TAU))
    for i in range(NUM_EPOCHS):
        index_micro, new_config = explore_configuration()
        _configs = CONFIGURATIONS.copy()
        # uncomment below to explore for new configurations
        _configs[index_micro] = new_config # set to new config to explore
        logging.debug("patching deployment {}, with {} cores and {} mem".format(new_config[0], new_config[1], new_config[2]))
        patch_deployment(new_config[0], new_config[1], new_config[2])
        is_cluster_ready(v1)
        logging.debug("success patching, running workload")
        exec_time = run_workload(_configs, v1)
        new_objective = objective_function(exec_time, sum([i[1] for i in _configs]), sum([i[2] for i in _configs]))
        logging.debug("done workload with mean time {}ms, objective value {}".format(exec_time, new_objective))
        if random.random() < annealing_probability(old_objective, new_objective, TAU):
           logging.debug("Annealing ACCEPTED config {}, {}, {}".format(new_config[0], new_config[1], new_config[2]))
           old_objective = new_objective
           CONFIGURATIONS = _configs
        else:
           logging.debug("Annealing REJECTED config {}, {}, {}".format(new_config[0], new_config[1], new_config[2]))
        logging.debug("Config for {} is {} cores, {} mem".format(CONFIGURATIONS[index_micro][0], CONFIGURATIONS[index_micro][1], CONFIGURATIONS[index_micro][2]))
        
if __name__ == '__main__':
    main()
