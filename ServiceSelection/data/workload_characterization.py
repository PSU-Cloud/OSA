import numpy as np
import os
import time
import sys
import fileinput
from datetime import datetime
import signal



## PARAMS
global MIN_CORES, MAX_CORES, CORE_STEPS, MIN_MEM, MAX_MEM, MEM_STEPS, SPARK_CONFIG_FILEPATH

### Spark config filepath
SPARK_CONFIG_FILEPATH = "<INSERT FILEPATH TO SPARK CONFIG>"

### Core Experimental Range
MIN_CORES = 5
MAX_CORES = 200
CORE_STEPS = 5

### Mem Exprimental Range
MIN_MEM   = 1000
MAX_MEM   = 5000
MEM_STEPS = 250




def handler(signum, frame):
    print("ctrl + c: exit program...")
    exit()
signal.signal(signal.SIGINT, handler)

# cores is total number of cores used in the cluster
# mem is the memory allocated per executor in MB
def spark_executor_cores_and_memory(cores, mem):
    global SPARK_CONFIG_FILEPATH
    filepath = SPARK_CONFIG_FILEPATH
    for line in fileinput.input(filepath, inplace=True):
        if 'spark.cores.max' in line.split(' '):
            print('spark.cores.max    {}'.format(cores))
        elif 'spark.executor.memory' in line.split(' '):
            print('spark.executor.memory    {}M'.format(mem))
        else:
            print(line, end = '')
    

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("usage: python3 {} <workload path>".format(sys.argv[0]))
        exit()

    workload_path = sys.argv[1]
    
    output_filename = workload_path + '_char_' + str(datetime.now())
    with open(output_filename, "w") as fd:
        executions = []
        for core in range(MIN_CORES, MAX_CORES + 1, CORE_STEPS):
            for mem in range(MIN_MEM, MAX_MEM + 250, MEM_STEPS):
                time.sleep(1) # sleep for one second in case a ctrl + c has be made
                # change spark.conf file in HiBench
                spark_executor_cores_and_memory(core, mem)
                cmd = 'bash /{}/spark/run.sh'.format(workload_path)
                start_time = time.time()
                os.system(cmd)
                exec_time = time.time() - start_time
                fd.write("{},{},{}\n".format(core, mem, exec_time))

