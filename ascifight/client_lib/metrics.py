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


def step_factory(border: float, inner: float, outer: float) -> Callable[[float], float]:
    def step(distance: float) -> float:
        return inner if distance <= border else outer

    return step


class WeightsGenerator:
    def __init__(self, objects: Objects):
        self.objects = objects
        self.map_size = objects.rules.map_size
        self._logger = structlog.get_logger()

    def _distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        return numpy.sqrt(numpy.square(x1 - x2) + numpy.square(y1 - y2))

    def _weights_for_multiple_coordinates(
        self, items: list[tuple[Coordinates, Callable[[float], float]]]
    ) -> npt.NDArray[numpy.float16]:
        weights: npt.NDArray[numpy.float16] = numpy.zeros(
            (self.map_size, self.map_size), dtype=numpy.float16
        )
        for item in items:
            weight = self._weights_for_coordinates(item[0].x, item[0].y, item[1])
            weights = weights + weight
        return weights

    def _weights_for_coordinates(
        self, x: float, y: float, function: Callable[[float], float]
    ) -> npt.NDArray[numpy.float16]:
        weight: npt.NDArray[numpy.float16] = numpy.ndarray(
            (self.map_size, self.map_size), dtype=numpy.float16
        )
        for y_map in range(self.map_size):
            for x_map in range(self.map_size):
                distance = self._distance(x, y, x_map, y_map)
                weight[y_map][x_map] = function(distance)
        return weight

    def avoid_attackers(
        self,
        avoid_function: Callable[[float], float] = gaussian_factory(factor=3, sigma=2),
    ) -> npt.NDArray[numpy.float16]:
        killer_coordinates = [
            actor.coordinates
            for actor in self.objects.enemy_actors
            if actor.properties.attack > 0
        ]
        self._logger.debug("Avoiding killers.", coordinates=killer_coordinates)
        weights = self._weights_for_multiple_coordinates(
            [(coordinates, avoid_function) for coordinates in killer_coordinates]
        )
        return weights

    def guard_base(self, radius=5) -> npt.NDArray[numpy.float16]:
        home_base_coordinates = self.objects.home_base.coordinates
        guard_function = step_factory(4, 0, math.inf)
        self._logger.debug("Guarding base.")
        weights = self._weights_for_coordinates(
            home_base_coordinates.x, home_base_coordinates.y, guard_function
        )
        return weights

    def avoid_coordinates(
        self, x: float, y: float, avoid_function: Callable[[float], float]
    ) -> npt.NDArray[numpy.float16]:
        return self._weights_for_coordinates(x, y, avoid_function)


class BlockersGenerator:
    def __init__(
        self,
        objects: Objects,
        additional_blockers: list[Coordinates] | None = None,
    ) -> None:
        self.objects = objects
        self.map_size = objects.rules.map_size
        self._logger = structlog.get_logger()

    def standard_blockers(
        self,
        blocking_walls: bool = True,
        blocking_own_actors: bool = True,
        blocking_enemy_actors: bool = True,
        blocking_bases: bool = True,
    ) -> list[Coordinates]:
        blockers: list[Coordinates] = []
        if blocking_walls:
            blockers.extend([wall.coordinates for wall in self.objects.walls])
        if blocking_bases:
            blockers.extend([base.coordinates for base in self.objects.enemy_bases])
            blockers.append(self.objects.home_base.coordinates)
        if blocking_enemy_actors:
            blockers.extend([actor.coordinates for actor in self.objects.enemy_actors])
        if blocking_own_actors:
            blockers.extend([actor.coordinates for actor in self.objects.own_actors])
        return blockers


class Metric(ABC):
    def __init__(
        self,
        objects: Objects,
        blockers: list[Coordinates] | None = None,
        weights: npt.NDArray[numpy.float16] | None = None,
    ):
        self.objects = objects
        self.map_size = objects.rules.map_size

        self.blockers = (
            blockers
            if blockers
            else BlockersGenerator(self.objects).standard_blockers()
        )
        ones = numpy.ones((self.map_size, self.map_size), dtype=numpy.float16)
        self.weights = ones if weights is None else ones + weights

        self.distance_fields: dict[Coordinates, dict[Coordinates, float]] = {}
        self.paths: dict[tuple[Coordinates, Coordinates], list[Coordinates]] = {}

    def path_distance(self, origin: Coordinates, destination: Coordinates) -> float:
        """
        The distance between origin and destination in steps. If a path can not be
        found the distance is infinity.
        """
        distance = math.inf
        path = self.path(origin, destination)
        if destination in path:
            distance = len(path) - 1
        return distance

    def air_distance(self, origin: Coordinates, destination: Coordinates) -> float:
        """
        The distance between origin and destination absolute.
        """
        return abs(origin.x - destination.x) + abs(origin.y - destination.y)

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
        path = self.path(origin, destination)
        if path and len(path) > 1:
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
        map_size = self.objects.rules.map_size
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
        for i in range(self.map_size):
            for j in range(self.map_size):
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
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.grid: dijkstra.GridWithWeights = dijkstra.GridWithWeights(
            height=self.map_size,
            width=self.map_size,
            blockers=self.blockers,
            weights=self.weights,
        )

    def _distance_field(self, origin: Coordinates) -> dict[Coordinates, float]:
        _, distance_field = dijkstra.dijkstra_search(self.grid, origin, None)
        return distance_field

    def _path(self, origin: Coordinates, destination: Coordinates) -> list[Coordinates]:
        unblock_origin = False
        if origin in self.blockers:
            self.blockers.remove(origin)
            unblock_origin = True
        unblock_destination = False
        if destination in self.blockers:
            self.blockers.remove(destination)
            unblock_destination = True
        came_from, cost_so_far = dijkstra.dijkstra_search(
            self.grid, origin, destination
        )
        path = dijkstra.reconstruct_path(
            came_from, cost_so_far, start=origin, goal=destination
        )
        # dijkstra.draw_grid(
        #     self.grid,
        #     path=path,
        #     number=cost_so_far,
        #     start=origin,
        #     goal=destination,
        # )
        if unblock_origin:
            self.blockers.append(origin)
        if unblock_destination:
            self.blockers.append(destination)
        return path
