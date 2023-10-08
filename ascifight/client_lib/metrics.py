from abc import ABC, abstractmethod
import math
from typing import Callable

import structlog
import numpy
import numpy.typing as npt

from ascifight.board.data import Coordinates
from ascifight.client_lib.object import Objects

from ascifight.board.actions import Directions
import ascifight.client_lib.dijkstra as dijkstra


def gaussian_factory(factor: float, sigma: float) -> Callable[[float], float]:
    def gaussian(distance: float) -> float:
        x = distance / sigma
        return factor * math.exp(-x * x / 2.0)

    return gaussian


def linear_factory(factor: float, negative_slope: float) -> Callable[[float], float]:
    def linear(distance: float) -> float:
        return min(0, factor - negative_slope * distance)

    return linear


class PathTopology:
    def __init__(
        self,
        objects: Objects,
        blocking_walls: bool = True,
        blocking_own_actors: bool = True,
        blocking_enemy_actors: bool = True,
        blocking_bases: bool = True,
        additional_blockers: list[Coordinates] | None = None,
        additional_weights: npt.NDArray[numpy.float16] | None = None,
    ) -> None:
        self.objects = objects
        self.map_size = objects.rules.map_size
        self.blocking_walls = blocking_walls
        self.blocking_enemy_actors = blocking_enemy_actors
        self.blocking_own_actors = blocking_own_actors
        self.blocking_bases = blocking_bases
        self.blockers = self._blockers(additional_blockers)
        self.weights = self._weights(additional_weights)
        self._logger = structlog.get_logger()

    def _blockers(
        self, additional_blockers: list[Coordinates] | None
    ) -> list[Coordinates]:
        blockers: list[Coordinates] = []
        if self.blocking_walls:
            blockers.extend([wall.coordinates for wall in self.objects.walls])
        if self.blocking_bases:
            blockers.extend([base.coordinates for base in self.objects.enemy_bases])
            blockers.append(self.objects.home_base.coordinates)
        if self.blocking_enemy_actors:
            blockers.extend([actor.coordinates for actor in self.objects.enemy_actors])
        if self.blocking_own_actors:
            blockers.extend([actor.coordinates for actor in self.objects.own_actors])
        if additional_blockers:
            blockers.extend(additional_blockers)
        return blockers

    def _weights(
        self, additional_weights: npt.NDArray[numpy.float16] | None
    ) -> npt.NDArray[numpy.float16]:
        weights = numpy.ones((self.map_size, self.map_size), dtype=numpy.float16)
        if additional_weights:
            weights = weights + additional_weights
        return weights

    def _distance(self, x: int, y: int, coordinates: Coordinates) -> float:
        return numpy.sqrt(
            numpy.square(x - coordinates.x) + numpy.square(y - coordinates.y)
        )

    def _create_weights(
        self, items: list[tuple[Coordinates, Callable[[float], float]]]
    ) -> npt.NDArray[numpy.float16]:
        weights: npt.NDArray[numpy.float16] = numpy.zeros(
            (self.map_size, self.map_size), dtype=numpy.float16
        )
        for item in items:
            weight: npt.NDArray[numpy.float16] = numpy.ndarray(
                (self.map_size, self.map_size), dtype=numpy.float16
            )
            for y in range(self.map_size):
                for x in range(self.map_size):
                    distance = self._distance(x, y, item[0])
                    weight[y][x] = item[1](distance)
            weights = weights + weight
        return weights


class AvoidKillerTopology(PathTopology):
    def __init__(
        self,
        *args,
        avoid_function: Callable[[float], float] = gaussian_factory(factor=3, sigma=2),
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        killer_coordinates = [
            actor.coordinates
            for actor in self.objects.enemy_actors
            if actor.properties.attack > 0
        ]
        self._logger.debug("Avoiding killers.", coordinates=killer_coordinates)
        weights = self._create_weights(
            [(coordinates, avoid_function) for coordinates in killer_coordinates]
        )
        self.weights = self.weights + weights


class Metric(ABC):
    def __init__(self, topology: PathTopology):
        self.topology = topology
        self.distance_fields: dict[Coordinates, dict[Coordinates, float]] = {}
        self.paths: dict[tuple[Coordinates, Coordinates], list[Coordinates]] = {}

    def distance(self, origin: Coordinates, destination: Coordinates) -> float:
        """
        The distance between origin and destination in steps. If a path can not be
        found the distance is infinity.
        """
        distance = math.inf
        if path := self.path(origin, destination):
            distance = len(path)
        return distance

    def distance_field(self, origin: Coordinates) -> dict[Coordinates, float]:
        """
        The weighted distance to each map coordinates from an origin coordinate.
        If no weights are given the distances are equal to the path length.
        If weights are given, the distance depends on the weights used
        """
        if origin in self.distance_fields:
            result = self.distance_fields[origin]
        else:
            result = self._distance_field(origin)
            self.distance_fields[origin] = result
        return result

    def path(self, origin: Coordinates, destination: Coordinates) -> list[Coordinates]:
        """
        The shortest path from an origin coordinate to a destination coordinate.
        """
        if (origin, destination) in self.paths:
            result = self.paths[(origin, destination)]
        else:
            result = self._path(origin, destination)
            self.paths[(origin, destination)] = result
        return result

    def next_direction(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> Directions | None:
        """
        The next direction to move on the shortest path from the origin coordinate to
        the destination coordinate.
        IF a path can not be found, the next direction is None.
        """
        direction = None
        if path := self.path(origin, destination):
            next = path[1]

            if origin.x == next.x:
                if next.y > origin.y:
                    direction = Directions.up
                else:
                    direction = Directions.down
            else:
                if next.x > origin.x:
                    direction = Directions.right
                else:
                    direction = Directions.left
        return direction

    @abstractmethod
    def _distance_field(self, origin: Coordinates) -> dict[Coordinates, float]:
        pass

    def _path(self, origin: Coordinates, destination: Coordinates) -> list[Coordinates]:
        path: list[Coordinates] = [destination]
        distance_field = self.distance_field(origin)
        next = destination
        while next != origin:
            neighbors = self._neighbors(path[-1])
            distances = [
                (distance_field[coordinates], coordinates) for coordinates in neighbors
            ]
            next = sorted(distances, key=lambda x: x[0])[0][1]
            path.append(next)
        path.reverse()
        return path

    def _in_bounds(self, coordinates: tuple[int, int]) -> bool:
        x, y = coordinates
        map_size = self.topology.map_size
        return 0 <= x < map_size and 0 <= y < map_size

    def _neighbors(self, coordinates: Coordinates) -> list[Coordinates]:
        (x, y) = coordinates.x, coordinates.y
        coords = filter(
            self._in_bounds, [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        )
        return [Coordinates(x=x, y=y) for x, y in coords]


class BasicMetric(Metric):
    def _distance_field(self, origin: Coordinates) -> dict[Coordinates, float]:
        distance_field: dict[Coordinates, float] = {}
        for i in range(self.topology.map_size):
            for j in range(self.topology.map_size):
                coordinates = Coordinates(x=i, y=j)
                distance = self._distance(origin, coordinates)
                distance_field[coordinates] = distance
        return distance_field

    def _distance(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> int:
        """
        Calculate the distance in steps between origin and destination coordinates.
        """
        x, y = self._distance_vector(origin, destination)
        return abs(x) + abs(y)

    def _distance_vector(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> tuple[int, int]:
        """
        Calculate the distance vector between origin and destination coordinates.
        """
        x = destination.x - origin.x
        y = destination.y - origin.y
        return x, y


class DijkstraMetric(Metric):
    def __init__(self, topology: PathTopology) -> None:
        super().__init__(topology)
        self.grid: dijkstra.GridWithWeights = dijkstra.GridWithWeights(
            height=self.topology.map_size,
            width=self.topology.map_size,
            blockers=self.topology.blockers,
            weights=self.topology.weights,
        )

    def _distance_field(self, origin: Coordinates) -> dict[Coordinates, float]:
        _, distance_field = dijkstra.dijkstra_search(self.grid, origin, None)
        return distance_field

    def _path(self, origin: Coordinates, destination: Coordinates) -> list[Coordinates]:
        unblock_origin = False
        if origin in self.topology.blockers:
            self.topology.blockers.remove(origin)
            unblock_origin = True
        unblock_destination = False
        if destination in self.topology.blockers:
            self.topology.blockers.remove(destination)
            unblock_destination = True
        came_from, cost_so_far = dijkstra.dijkstra_search(
            self.grid, origin, destination
        )
        path = dijkstra.reconstruct_path(came_from, start=origin, goal=destination)
        # dijkstra.draw_grid(
        #     self.grid,
        #     path=dijkstra.reconstruct_path(came_from, start=origin, goal=destination),
        #     number=cost_so_far,
        #     start=origin,
        #     goal=destination,
        # )
        if unblock_origin:
            self.topology.blockers.append(origin)
        if unblock_destination:
            self.topology.blockers.append(destination)
        return [i for i in path if i is not None]
