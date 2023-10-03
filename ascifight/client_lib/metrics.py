from abc import ABC, abstractmethod

import ascifight.board.data as data
from ascifight.routers.states import StateResponse

from ascifight.board.actions import Directions


class Metric(ABC):
    def __init__(self, game_state: StateResponse):
        self.game_state = game_state

    @abstractmethod
    def distance(self, origin: data.Coordinates, destination: data.Coordinates) -> int:
        pass

    @abstractmethod
    def next_direction(
        self,
        origin: data.Coordinates,
        destination: data.Coordinates,
    ) -> Directions:
        pass


class BasicMetric(Metric):
    def distance(
        self,
        origin: data.Coordinates,
        destination: data.Coordinates,
        game_state: StateResponse | None = None,
    ) -> int:
        """
        Calculate the distance in steps between origin and destination coordinates.
        """
        x, y = self._distance_vector(origin, destination)
        return abs(x) + abs(y)

    def next_direction(
        self,
        origin: data.Coordinates,
        destination: data.Coordinates,
    ) -> Directions:
        """
        Calculate direction given origin coordinates and destination coordinates.
        """
        direction = Directions.up

        x, y = self._distance_vector(origin, destination)

        if abs(x) == abs(y):
            if x > 0 and y > 0:
                direction = Directions.up
            elif x > 0 and y < 0:
                direction = Directions.right
            elif x < 0 and y > 0:
                direction = Directions.left
            elif x < 0 and y < 0:
                direction = Directions.down

        elif abs(y) > abs(x):
            if y > 0:
                direction = Directions.up
            else:
                direction = Directions.down
        else:
            if x > 0:
                direction = Directions.right
            else:
                direction = Directions.left

        return direction

    def _distance_vector(
        self,
        origin: data.Coordinates,
        destination: data.Coordinates,
    ) -> tuple[int, int]:
        """
        Calculate the distance vector between origin and destination coordinates.
        """
        x = destination.x - origin.x
        y = destination.y - origin.y
        return x, y
