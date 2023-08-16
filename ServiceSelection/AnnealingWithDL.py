from matplotlib.ft2font import LOAD_IGNORE_GLOBAL_ADVANCE_WIDTH
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from matplotlib import cm
import numpy as np
import random

# Parameters
global CLOUD_PRICING, ALPHA_1, ALPHA_2, ALPHA_3, LAMDA
CLOUD_PRICING = [0.034, 0.0385, 0.144, 0.0504]
# uncomment  the following line for modified VM pricing
CLOUD_PRICING = [0.034, 0.0385, 0.04445, 0.0504]
# Lambda to weight operational cost vs. performance
LAMDA = 30

## Annealing classes
class Configuration:
    """A configuration for a job"""
    def __init__(self, parameters=[]):
        self.parameters = parameters

class ConfigurationParameter:
    """A configuration parameter with its domain of values"""
    def __init__(self, domain=[], step_size=1, value=None, describ=""):
        self.domain = domain
        self.value = value
        self.describ = describ
        self.step_size = step_size

    def explore_neighbor(self):
        index = self.domain.index(self.value)
        new_value_index = index + (self.step_size if random.random() < 0.5 else -self.step_size)
        if new_value_index > len(self.domain) - 1:
            new_value_index = len(self.domain) - 1
        elif new_value_index < 0:
            new_value_index = 0
        _new_config = ConfigurationParameter(domain=self.domain,
                                      value=self.domain[new_value_index],
                                      describ=self.describ)
        return _new_config


class ResourceManagerWithAnnealing(object):
    """Manage number of executors based of object sizes"""
    def __init__(self, workload_char, configuration, tau=1):
        super(ResourceManagerWithAnnealing, self).__init__()
        self.current_configuration = configuration
        self.tau = tau

        #TODO: do better job
        self.workload_char = workload_char
        # it is set to None if this is the first job to run
        self.old_objective = None

    def submit_job(self, workload):
        # exploraing for different paramters in the configuration
        new_conf = Configuration(parameters=[])
        for param in self.current_configuration.parameters:
            new_param = param.explore_neighbor()
            new_conf.parameters.append(new_param)

        new_exec_time = self.run_job(workload, new_conf)
        new_objective = self.objective_func(workload, new_conf)
        # XXX: accept the first conifugration for first job
        if self.old_objective is None:
            self.current_configuration = new_conf
            self.old_objective = new_objective
        elif random.random() < self.annealing_probability(self.old_objective, new_objective, self.tau):
            self.current_configuration = new_conf
            self.old_objective = new_objective

        return new_conf, new_exec_time

    def simulate(self, workload, iterations, tau=None):
        _executions = []
        self.tau = tau if tau is not None else self.tau
        for i in range(iterations):
            print("{}/{}".format(i+1, iterations), end="\r")
            ## pick a workload based on alpha
            new_conf, exec_time = self.submit_job(workload)
            _executions.append((new_conf, self.current_configuration, self.old_objective, exec_time))
        return _executions

    def objective_func(self, workload, config):
        return float(workload[workload.cores == config.parameters[0].value[0]][workload.mem == config.parameters[0].value[1]].obj)

    def annealing_probability(self, y1, y2, tau):
        return np.exp((-max(y2-y1,0))/tau)

    def run_job(self, workload, config):
        executor_cores = config.parameters[0].value[0]
        memory_size = config.parameters[0].value[1]
        return float(workload[workload.cores == executor_cores][workload.mem == memory_size].time)


#######################
## Helper methods
#######################
def weighted_choice(weights):
    choice = random.random() * sum(weights)
    for i, w in enumerate(weights):
        choice -= w
        if choice < 0:
            return i


def plot_char(fig_num, workload, title=""):
    fig = plt.figure(fig_num)
    ax = plt.axes(projection='3d')

    ax.plot_trisurf (workload.cores, [(i* 5)/1000 for i in workload.mem], workload.time, cmap=cm.jet)

    ax.set_title(title)
    ax.set_xlabel("Total Cores")
    ax.set_ylabel("Total Memory (GB)")
    ax.set_zlabel("execution_time")


def plot_obj(fig_num, workload, title="", isCmap = True):
    fig = plt.figure(fig_num)
    ax = plt.axes(projection='3d')


    if isCmap:
        ax.plot_trisurf (workload.cores, [(i* 5)/1000 for i in workload.mem], workload.obj, cmap=cm.jet)
    else:
        ax.plot_trisurf (workload.cores, [(i* 5)/1000 for i in workload.mem], workload.obj)

    ax.set_title(title)
    ax.set_xlabel("Total Cores", fontweight="bold")
    ax.set_ylabel("Total Memory (GB)", fontweight="bold")
    ax.set_zlabel("Objective", fontweight="bold")
    ax.axes.zaxis.set_ticks([])


def scatter_executions_obj(fig_num, workload, executions, title=""):
    fig = plt.figure(fig_num)
    ax = plt.axes(projection='3d')

    ax.plot_trisurf (workload.cores, [i/1000 for i in workload.mem], workload.obj, alpha=0.25)

    cores = [nc.parameters[0].value[0] for nc, _, _, _ in executions]
    mems  = [nc.parameters[0].value[1] for nc, _, _, _ in executions]
    objs  = []
    for i, _cores in enumerate(cores):
        # print(workload[workload.cores == _cores][workload.mem == mems[i]].obj)
        objs.append(float(workload[workload.cores == _cores][workload.mem == mems[i]].obj))
    ax.scatter3D(cores, [i/1000 for i in mems], objs, color="red")

    # ax.set_title(title)
    ax.set_xlabel("Total Cores", fontweight="bold")
    ax.set_ylabel("Total Memory (GB)", fontweight="bold")
    ax.set_zlabel("Objective", fontweight="bold")
    ax.set_ylim([4, 120])
    ax.axes.zaxis.set_ticks([])
    


####### Specify objectives #######
def objective(k, exec_time, base):
    _lamda = LAMDA
    cost = lambda x: base * x
    return exec_time + _lamda * cost(k)

def objective_2(cores, mem, time):
    price_per_core = 1
    price_per_mem  = 0.5
    _lamda = 5
    cost = lambda c,m,t: t * (c * price_per_core + m * price_per_mem)
    return time + _lamda * cost(cores, mem, time)


def parse_file(filename):
    workload = pd.read_csv(filename)
    return workload

def parse_file_2(filename):
    workload = pd.read_csv(filename)
    _bases = [0.034, 0.0385, 0.0504, 0.156]
    for index, base in enumerate(_bases):
        _objective = lambda row: objective_2(row['cores'], row['mem'], row['time'])
        workload['obj{}'.format(index)] = workload.apply(_objective, axis=1)
    return workload


def get_objs(workload, bases):
    objs   = []
    for e in workload.iterrows():
        index = e[0]
        c = e[1].cores
        t = e[1].time
        objs.append(objective(c, t, bases[index]))
    return objs


if __name__ == '__main__':

    _MNIST = parse_file("./data/DLExample/dl_MNIST.csv")
    bases = []
    for _ in range(15):
        for k in CLOUD_PRICING:
            bases.append(k)
    
    MNIST_obj = get_objs(_MNIST, bases)
    cores  = list(_MNIST.cores)
    mems   = list(_MNIST.mem)

    _MNIST = pd.DataFrame({'cores': cores, 'mem':mems, 'time': list(_MNIST.time), 'obj':MNIST_obj})

    
    iterations = 5000 # number of simulated jobs submitted
    cores_sim = cores
    memory_sizes = mems
    _configs = [ (cores[i], mems[i]) for i in range(len(cores))]
    cores_step = 1
    mem_step = 1

    for i, tau in enumerate([1]):
        conf = Configuration()
        conf.parameters.append(ConfigurationParameter(domain=_configs, step_size=1, value=_configs[0], describ="both mem and cpu"))
        myRM = ResourceManagerWithAnnealing(_MNIST, configuration=conf, tau=tau)
        executions = myRM.simulate(_MNIST, iterations, tau)
        _objs = []
        for e, _, _, _ in executions:
            _cores = e.parameters[0].value[0]
            _mem   = e.parameters[0].value[1]
            _objs.append(_MNIST[_MNIST.cores == _cores][_MNIST.mem == _mem].obj)

        plt.plot(range(len(_objs)), _objs, color="blue", label="Computed Objective")
        plt.ylim([20, _MNIST.obj.max() + 5])
        plt.plot(range(len(_objs)), [_MNIST.obj.min() for _ in range(len(_objs))], label="Minimum Objective", color="green", linewidth=3)
        plt.plot(range(len(_objs)), [_MNIST.obj.max() for _ in range(len(_objs))], label="Maximum Objective", color="red", linewidth=3)
        plt.legend(loc="upper center", ncol=3)
        plt.xlabel("Job IDs", fontweight="bold")
        plt.ylabel("Objective", fontweight="bold")

    plt.show()

    exit()



    