from random import uniform, choice
from math import exp, log, sqrt
from time import time
import json
#from .main import VehicleRoutingProblem
import logging
import bisect

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class HyperHeuristic:
    """
    HyperHeuristic class manages the high-level heuristic strategies
    Args: 
        scaling_factor (float): 
            parameter deciding the balance between exploration and explotation
        time_limit (float): 
            total time limit for the algorithm
        current_objective_value (float): 
            the objective value for previous iteration
        new_objective_value (float): 
            the objective value for the current iteration
        inf (float): 
            very large number 
        iteration_counter (int): 
            counts the number of iterations
        initialisation (bool): 
            initialisation parameter 
        heur_names (list, str): 
            names of heurestic strategies 
        pool (list, int: 
            the pool of heurestics, indexed by integers
        q (list, floats): 
            list of heuristic quality (rank)
        r (list, floats): 
            list of average improvements
        n (list, int): 
            list of iteration counters
        heuristic_points (list, floats): 
            list of points for each heurestic at the current timepoint
        improvements (dict, dict, floats):
            a dictionary with keys indexed by heuristics with values equal to dictionaries with rewards
        current_heuristic (int):
            the currently applied heuristic
    """
    def __init__(self,
                 poolsize: int = 4,
                 start_heur: int = 0,
                 scaling_factor: float = 0.5,
                 offline_learning: bool = False,
                 performance_measure="Weighted average",
                 acceptance_type="Accept all"):

        #params
        self.scaling_factor = scaling_factor
        self.theta = 1
        #self.decay_factor = None

        #self.time_limit = None
        self.current_objective_value = None
        self.new_objective_value = None
        self.produced_column = None

        self.inf = 1E10

        #consider
        #self.iteration_counter = 0  # maybe one for each heuristic?
        self.initialisation = True

        #high level data
        self.performence_measure_list = [
            "Relative improvement", "Weighted average"
        ]
        self.heur_names = ["BestPaths", "BestEdges1", "BestEdges2", "Exact"]
        self.pool = [i for i in range(poolsize)]
        self.q = [0] * poolsize
        self.r = [0] * poolsize
        self.n = [0] * poolsize
        self.added_columns = [0] * poolsize
        self.exp_list = [0] * poolsize
        self.d = 0
        self.d_max = 0
        self.total_n = 0
        self.average_runtime = 0
        self.step = 0.02
        self.n_exact = 0

        #weighed average approach
        self.runtime_dist = []
        self.objective_decrease_list = [0] * poolsize
        self.norm_objective_decrease_list = [0] * poolsize
        self.active_dict = {}
        self.norm_runtime_list = [0] * poolsize
        self.last_runtime_list = [0] * poolsize
        self.total_objective_decrease = 0.0

        #Consider setting to zero
        self.heuristic_points = [self.inf] * poolsize
        #consider
        self.current_heuristic = start_heur
        self.loaded_parameters = {}

        #total time
        self.timestart = None
        self.timeend = None
        self.last_runtime = None
        self.time_windows = None
        self.start_computing_average = 1

        #Settings
        self.performance_measure = performance_measure
        self.acceptance_type = acceptance_type

    def set_current_objective(self, objective: float = None):
        """
        sets current_objective_value
        """
        self.current_objective_value = objective

    def set_initial_time(self):
        self.timeend = time()

    def pick_heurestic(self, heuristic: int = None):
        """
        Sets the chosen heuristic based on selection points
        """
        # force a particular heuristic
        if not heuristic == None:
            return heuristic

        # set performance measure
        if self.performance_measure == "Relative improvement":

            #before the number of iterations is high enough
            if self.total_n < self.start_computing_average:
                return choice(self.heur_names[0:2])

        elif self.performance_measure == "Weighted average":
            pass

        #choose according to MAB
        maxval = max(self.heuristic_points)
        best_heuristics = [
            i for i, j in enumerate(self.heuristic_points) if j == maxval
        ]
        if len(best_heuristics) == 1:
            self.current_heuristic = best_heuristics[0]
        else:
            self.current_heuristic = choice(best_heuristics)
            #vil den ikke så og si alltid bare være en?
        return self.heur_names[self.current_heuristic]

    def update_scaling_factor(self):
        if self.obj_has_decreased and self.produced_column:
            self.theta = 0.99
        else:
            self.theta = max(self.theta - self.step, self.step)

    def current_performance(
        self,
        new_objective_value: float = None,
        produced_column: bool = None,
        active_columns: dict = None,
    ):
        """Updates the variables at the current iteration

        """
        #   computes last time
        self.timestart = self.timeend
        self.timeend = time()
        self.last_runtime = self.timeend - self.timestart

        self.last_runtime_list[self.current_heuristic] = self.last_runtime

        #update choices list
        self.n[self.current_heuristic] += 1

        # column produced
        self.produced_column = produced_column
        if produced_column:
            self.added_columns[self.current_heuristic] += 1

        #   objective function measure
        self.obj_has_decreased = self.current_objective_value - new_objective_value > 0

        if self.performance_measure == "Relative improvement":
            #   time measure
            if self.total_n > self.start_computing_average + 1:
                self.d = max((self.average_runtime - self.last_runtime) /
                             self.average_runtime * 100, 0)
                logger.info("Resolve count %s, improvement %s" %
                            (produced_column, self.d))
                if self.d > self.d_max:
                    self.d_max = self.d

                    logger.info(
                        "Column produced, average runtime %s and last runtime %s"
                        % (self.average_runtime, self.last_runtime))
                else:
                    self.d = 0

        if self.performance_measure == "Weighted average":

            # update the active columns
            self.active_dict = active_columns
            # update the decrease counter

            # insert new runtime into sorted list
            bisect.insort(self.runtime_dist, self.last_runtime)

            self.objective_decrease_list[self.current_heuristic] += max(
                self.current_objective_value - new_objective_value, 0)

            self.total_objective_decrease += max(
                self.current_objective_value - new_objective_value, 0)

            #update quality values
            for j in self.pool:
                if self.n[j] > 0:
                    self.exp_list[j] = sqrt(2 * log(sum(self.n)) / self.n[j])

                    index = bisect.bisect(self.runtime_dist,
                                          self.last_runtime_list[j])

                    self.norm_runtime_list[j] = (len(
                        self.runtime_dist) - index) / len(self.runtime_dist)
                    if self.total_objective_decrease > 0:
                        self.norm_objective_decrease_list[
                            j] = self.objective_decrease_list[
                                j] / self.total_objective_decrease

        self.set_current_objective(objective=new_objective_value)

    def move_acceptance(self):
        """
        Adds new improvement to the improvements dict and applies the move acceptance step

        Args:
            new_objective_value (float): new_objective_value. Defaults to None.

        Returns:
            (bool): if the move is accepted or not
        """

        update = True

        # different move acceptences
        if self.acceptance_type == "Accept all":
            return True

        # not finished
        elif self.acceptance_type == "Table":  #fikse d her
            if self.obj_has_decreased:
                pass
            elif self.obj_has_decreased:
                update = uniform(0, 1) < 0.5 * exp(self.d)
            elif not self.obj_has_decreased:
                update = uniform(0, 1) < 0.5 * exp(self.d)
            else:
                update = uniform(0,
                                 1) < 0.1 * exp(self.d)  #både punishe og øke

        elif self.acceptance_type == "objective_threshold":
            if self.obj_has_decreased:
                return True
            else:
                return uniform(0, 1) < exp(self.d)
        return update

    def reward(self, y, lower_bound=True):
        """
        Modify the improvement
        """
        # if there is stagnation, set improvement to small number
        if lower_bound:
            x = min(0.1 * self.d_max, y)
        else:
            x = y

        if y > 0:
            if self.obj_has_decreased and self.produced_column:
                x *= 1.5
            elif self.obj_has_decreased and not self.produced_column:
                x *= 1.2
            elif not self.obj_has_decreased and self.produced_column:
                x *= 1.2
            else:
                x *= 0.9
        return x

    def update_parameters(self):
        """Updates the high-level parameters
        """
        # measure time and add to weighted average

        i = self.current_heuristic

        self.update_scaling_factor()

        self.total_n += 1

        #compute average of runtimes

        if self.performance_measure == "Relative improvement":

            if self.total_n > self.start_computing_average:
                reduced_n = (self.total_n - self.start_computing_average) % 10
                if reduced_n == 0:
                    self.average_runtime = self.last_runtime
                else:
                    self.average_runtime = self.average_runtime * (
                        reduced_n -
                        1) / (reduced_n) + 1 / (reduced_n) * self.last_runtime

                #store old values
                old_q = self.q[i]
                old_n = self.n[i] - 1

                frozen = (old_q == 0 and old_n > 3)

                #average of improvements
                self.r[i] = self.r[i] * old_n / (old_n + 1) + 1 / (
                    old_n + 1) * self.reward(self.d, lower_bound=frozen)

                self.q[i] = (old_q + self.r[i]) / (old_n + 1)

                #compute heuristic points MAB-style
                for j in range(len(self.pool)):
                    if not self.n[j] == 0:
                        self.exp_list[j] = sqrt(2 * log(sum(self.n)) /
                                                self.n[j])
                        #OPTION1: theta f1 +  (1 - theta) f2
                        """ self.heuristic_points[
                            j] = self.theta * self.q[j] + self.scaling_factor(
                                1 - self.theta) * self.exp_list[
                                    j]  # consider adaptive selection """
                        #OPTION2: thetaf1 + f2
                        self.heuristic_points[j] = self.theta * self.q[
                            j] + self.scaling_factor * self.exp_list[
                                j]  # consider adaptive selection
            else:
                pass

        elif self.performance_measure == "Weighted average":
            # non basic column / total number non basic columns
            w0 = 0.5
            #normalised runtime
            w1 = 0.5
            #normalised spread
            w2 = 0.3
            #contribution to objective decrease
            w3 = 0.2
            #non basic columns / columns added
            w4 = 1
            sum_exp_list = sum(self.exp_list)
            active = sum(self.active_dict.values())

            for k in self.pool:
                #if heuristic has not been applied, let it be self.inf
                if self.n[k] > 0:
                    name = self.heur_names[k]

                    active_k = self.active_dict[name]

                    total_added = self.added_columns[k]

                    norm_runtime = self.norm_runtime_list[k]

                    norm_spread = 0
                    if not sum_exp_list == 0:
                        norm_spread = self.exp_list[k] / sum_exp_list

                    self.q[
                        k] = w0 * active_k / active + w1 * norm_runtime + w3 * self.norm_objective_decrease_list[
                            k] + w4 * active_k / total_added

                    self.heuristic_points[k] = self.theta * self.q[
                        k] + w2 * norm_spread * (1 - self.theta)
                else:
                    pass
