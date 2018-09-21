# -*- coding: utf-8 -*-

import logging
import threading
import os

import pandas as pd
import time
from spade.agent import Agent
from spade.template import Template

from .utils import load_class, StrategyBehaviour, status_to_str, request_path
from .protocol import REQUEST_PROTOCOL

logger = logging.getLogger("CoordinatorAgent")


class CoordinatorAgent(Agent):
    """
    Coordinator agent that manages the requests between taxis and passengers
    """

    def __init__(self, agentjid, password, http_port, backend_port):
        self.simulation_running = False
        self.simulation_time = None
        self.kill_simulator = threading.Event()
        self.kill_simulator.clear()
        self.lock = threading.RLock()

        self.coordinator_strategy = None
        self.taxi_strategy = None
        self.passenger_strategy = None

        self.http_port = http_port
        self.backend_port = backend_port
        self.template_path = os.path.dirname(__file__) + os.sep + "templates"

        self.knowledge_base = {}

        self.set("taxi_agents", {})
        self.set("passenger_agents", {})

        super().__init__(jid=agentjid, password=password)

    def setup(self):
        logger.info("Coordinator agent running")
        self.web.start(port=self.http_port, templates_path=self.template_path)
        logger.info("Web interface running at http://127.0.0.1:{}/app".format(self.http_port))

        self.web.add_get("app", self.index_controller, "index.html")
        self.web.add_get("entities", self.entities_controller, None)
        self.web.add_get("run", self.run_controller, None)
        self.web.add_get("clean", self.clean_controller, None)
        self.web.add_get("/generate/taxis/<int:ntaxis>/passengers/<int:npassengers>", self.generate_controller, None)

    @property
    def taxi_agents(self):
        """
        Gets the list of registered taxis

        Returns:
            list: a list of ``TaxiAgent``
        """
        return self.get("taxi_agents")

    @property
    def passenger_agents(self):
        """
        Gets the list of registered passengers

        Returns:
            list: a list of ``PassengerAgent``
        """
        return self.get("passenger_agents")

    def add_taxi(self, agent):
        """
        Adds a new ``TaxiAgent`` to the store.

        Args:
            agent (``TaxiAgent``): the instance of the TaxiAgent to be added
        """
        self.get("taxi_agents")[agent.name] = agent

    def add_passenger(self, agent):
        """
        Adds a new :class:`PassengerAgent` to the store.

        Args:
            agent (``PassengerAgent``): the instance of the PassengerAgent to be added
        """
        self.get("passenger_agents")[agent.name] = agent

    def set_strategies(self, coordinator_strategy, taxi_strategy, passenger_strategy):
        """
        Gets the strategy strings and loads their classes. This strategies are prepared to be injected into any
        new taxi or passenger agent.

        Args:
            coordinator_strategy (str): the path to the coordinator strategy
            taxi_strategy (str): the path to the taxi strategy
            passenger_strategy (str): the path to the passenger strategy
        """
        self.coordinator_strategy = load_class(coordinator_strategy)
        self.taxi_strategy = load_class(taxi_strategy)
        self.passenger_strategy = load_class(passenger_strategy)
        logger.debug("Loaded strategy classes: {}, {} and {}".format(self.coordinator_strategy,
                                                                     self.taxi_strategy,
                                                                     self.passenger_strategy))

    def run_simulation(self):
        """
        Starts the simulation
        """
        if not self.simulation_running:
            self.add_strategy(self.coordinator_strategy)
            for taxi in self.taxi_agents.values():
                taxi.add_strategy(self.taxi_strategy)
            for passenger in self.passenger_agents.values():
                passenger.add_strategy(self.passenger_strategy)

            self.simulation_running = True
            self.simulation_time = time.time()
            logger.info("Simulation started.")

    def get_simulation_time(self):
        """
        Returns the elapsed simulation time to the current time.
        If the simulation is not started it returns 0.

        Returns:
            float: the whole simulation time.
        """
        if not self.simulation_time:
            return 0
        return time.time() - self.simulation_time

    def add_strategy(self, strategy_class):
        """
        Injects the strategy by instantiating the ``strategy_class``.
        Since the ``strategy_class`` inherits from ``spade.Behaviour.Behaviour``,
        the new strategy is added as a behaviour to the agent.

        Args:
            strategy_class (class): the class to be instantiated.
        """
        template = Template()
        template.set_metadata("protocol", REQUEST_PROTOCOL)
        self.add_behaviour(strategy_class(), template)

    def request_path(self, origin, destination):
        """
        Requests a path to the RouteAgent.

        Args:
            origin (list): the origin coordinates (lon, lat)
            destination (list): the target coordinates (lon, lat)

        Returns:
            list, float, float: the path as a list of points, the distance of the path, the estimated duration of the path
        """
        return request_path(self, origin, destination)

    async def index_controller(self, request):
        """
        Web controller that returns the index page of the simulator.

        Returns:
            dict: the name of the template, the data to be pre-processed in the template
        """
        return {"port": self.backend_port}

    async def run_controller(self, request):
        """
        Web controller that starts the simulator.

        Returns:
            dict: no template is returned since this is an AJAX controller, an empty data dict is returned
        """
        self.run_simulation()
        return {}

    async def generate_controller(self, request):
        pass

    async def entities_controller(self, request):
        """
        Web controller that returns a dict with the entities of the simulator and their statuses.

        Example of the entities returned data::

            {
                "passengers": [
                    {
                        "status": 24,
                        "taxi": "taxi2@127.0.0.1",
                        "dest": [ 39.463356, -0.376463 ],
                        "waiting": 3.25,
                        "position": [ 39.460568, -0.352529 ],
                        "id": "michaelstewart"
                    }
                ],
                "taxis": [
                    {
                        "status": 11,
                        "passenger": "michaelstewart@127.0.0.1",
                        "assignments": 1,
                        "path": [
                                 [ 39.478328, -0.406712 ],
                                 [ 39.478317, -0.406814 ],
                                 [ 39.460568, -0.352529 ]
                                ],
                        "dest": [ 39.460568, -0.352529 ],
                        "position": [ 39.468131, -0.39685 ],
                        "speed": 327.58,
                        "id": "taxi2",
                        "distance": "6754.60"
                    }
                ],
                "stats": {
                    "totaltime": "-1.00",
                    "waiting": "3.25",
                    "finished": False,
                    "is_running": True
                },
                "tree": {
                    "name": "Agents",
                    "children": [
                        {
                            "count": "1",
                            "name": "Taxis",
                            "children": [ { "status": 11, "name": " taxi2", "icon": "fa-taxi" } ]
                        },
                        {
                            "count": "1",
                            "name": "Passengers",
                            "children": [ { "status": 24, "name": " michaelstewart", "icon": "fa-user" } ]
                        }
                    ]
                },
                "authenticated": False
            }

        Returns:
            dict:  no template is returned since this is an AJAX controller, a dict with the list of taxis, the list of passengers, the tree view to be showed in the sidebar and the stats of the simulation.
        """
        result = {
            "taxis": [taxi.to_json() for taxi in self.taxi_agents.values()],
            "passengers": [passenger.to_json() for passenger in self.passenger_agents.values()],
            "tree": self.generate_tree(),
            "stats": self.get_stats()
        }
        return result

    def clean_controller(self, request):
        """
        Web controller that resets the simulator to a clean state.

        Returns:
            dict: no template is returned since this is an AJAX controller, a dict with status=done
        """
        self.stop_agents()
        self.set("taxi_agents", {})
        self.set("passenger_agents", {})
        return {"status": "done"}

    def stop_agents(self):
        """
        Stops the simulator and all the agents
        """
        self.kill_simulator.set()
        with self.lock:
            for name, agent in self.taxi_agents.items():
                logger.info("Stopping taxi {}".format(name))
                agent.stop()
        with self.lock:
            for name, agent in self.passenger_agents.items():
                logger.info("Stopping passenger {}".format(name))
                agent.stop()

    def generate_tree(self):
        """
        Generates the tree view in JSON format to be showed in the sidebar.

        Returns:
            dict: a dict with all the agents in the simulator, with their name, status and icon.
        """
        tree = {
            "name": 'Agents',
            "children": [
                {
                    "name": "Taxis",
                    "count": "{}".format(len(self.taxi_agents)),
                    "children": [
                        {
                            "name": " {}".format(i.getName().split("@")[0]),
                            "status": i.status,
                            "icon": "fa-taxi"
                        } for i in self.taxi_agents.values()
                    ]
                },
                {
                    "name": "Passengers",
                    "count": "{}".format(len(self.passenger_agents)),
                    "children": [
                        {
                            "name": " {}".format(i.getName().split("@")[0]),
                            "status": i.status,
                            "icon": "fa-user"
                        } for i in self.passenger_agents.values()
                    ]
                },

            ]
        }
        return tree

    def get_stats(self):
        """
        Generates the stats of the simulation in JSON format.

        Examples::

            {
                "totaltime": "12.25",
                "waiting": "3.25",
                "finished": False,
                "is_running": True
            }

        Returns:
            dict: a dict with the total time, waiting time, is_running and finished values

        """

        def avg(array):
            """
            Makes the average of an array without Nones.
            Args:
                array (list): a list of floats and Nones

            Returns:
                float: the average of the list without the Nones.
            """
            array_wo_nones = filter(None, array)
            return (sum(array_wo_nones, 0.0) / len(array_wo_nones)) if len(array_wo_nones) > 0 else 0.0

        if len(self.passenger_agents) > 0:
            waiting = avg([passenger.get_waiting_time() for passenger in self.passenger_agents.values()])
            total = avg([passenger.total_time() for passenger in self.passenger_agents.values()])
        else:
            waiting, total = 0, 0

        return {
            "waiting": "{0:.2f}".format(waiting),
            "totaltime": "{0:.2f}".format(total),
            "finished": self.is_simulation_finished(),
            "is_running": self.simulation_running
        }

    def get_passenger_stats(self):
        """
        Creates a dataframe with the simulation stats of the passengers
        The dataframe includes for each passenger its name, waiting time, total time and status.

        Returns:
            ``pandas.DataFrame``: the dataframe with the passengers stats.
        """
        try:
            names, waitings, totals, statuses = zip(*[(p.getName(), p.get_waiting_time(),
                                                       p.total_time(), status_to_str(p.status))
                                                      for p in self.passenger_agents.values()])
        except ValueError:
            names, waitings, totals, statuses = [], [], [], []

        df = pd.DataFrame.from_dict({"name": names, "waiting_time": waitings, "total_time": totals, "status": statuses})
        return df

    def get_taxi_stats(self):
        """
        Creates a dataframe with the simulation stats of the taxis
        The dataframe includes for each taxi its name, assignments, traveled distance and status.

        Returns:
            ``pandas.DataFrame``: the dataframe with the taxis stats.
        """
        try:
            names, assignments, distances, statuses = zip(*[(t.getName(), t.num_assignments,
                                                             "{0:.2f}".format(sum(t.distances)),
                                                             status_to_str(t.status))
                                                            for t in self.taxi_agents.values()])
        except ValueError:
            names, assignments, distances, statuses = [], [], [], []
        df = pd.DataFrame.from_dict({"name": names,
                                     "assignments": assignments,
                                     "distance": distances,
                                     "status": statuses})
        return df

    def is_simulation_finished(self):
        """
        Checks whether the simulation has finished or not.
        A simulation is finished if all passengers are at their destinations.

        Returns:
            bool: whether the simulation has finished or not.
        """
        return all([passenger.is_in_destination() for passenger in self.passenger_agents.values()])


class CoordinatorStrategyBehaviour(StrategyBehaviour):
    """
    Class from which to inherit to create a coordinator strategy.
    You must overload the :func:`_process` method

    Helper functions:
        * :func:`get_taxi_agents`
        * :func:`get_passenger_agents`
    """

    async def on_start(self):
        self.logger = logging.getLogger("CoordinatorStrategy")
        self.logger.debug("Strategy {} started in coordinator".format(type(self).__name__))

    def get_taxi_agents(self):
        """
        Gets the list of registered taxis

        Returns:
            list: a list of ``TaxiAgent``
        """
        return self.get("taxi_agents").values()

    def get_passenger_agents(self):
        """
        Gets the list of registered passengers

        Returns:
            list: a list of ``PassengerAgent``
        """
        return self.get("passenger_agents").values()

    async def run(self):
        raise NotImplementedError
