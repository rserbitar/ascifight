from collections import defaultdict
from typing import Sequence, TypeVar

import ascifight.board.data as data
from ascifight.routers.states import (
    BaseDescription,
    StateResponse,
    ActorDescription,
    FlagDescription,
    WallDescription,
)
from ascifight.board.actions import Directions
import ascifight.client_lib.metrics as metrics


"""
Basic orientation and navigation
"""


def destination_coordinates(
    origin: data.Coordinates,
    direction: Directions,
    map_size: int,
) -> data.Coordinates:
    """
    Calculate destination coordinates given current coordinates and a direction and map
    size.
    """
    new_coordinates = data.Coordinates(x=origin.x, y=origin.y)
    match direction:
        case direction.right:
            new_coordinates.x = min(origin.x + 1, map_size - 1)
        case direction.left:
            new_coordinates.x = max(origin.x - 1, 0)
        case direction.up:
            new_coordinates.y = min(origin.y + 1, map_size - 1)
        case direction.down:
            new_coordinates.y = max(origin.y - 1, 0)
    return new_coordinates


class Objects:
    """
    Basic objects.
    """

    def __init__(self, game_state: StateResponse, own_team: str):
        self.game_state = game_state
        self.own_team = own_team
        self.home_base = self._home_base()
        self.own_flag = self._own_flag()
        self.own_actors = self._own_actors()
        self.enemy_actors = self._enemy_actors()
        self.enemy_flags = self._enemy_flags()
        self.walls = self._walls()
        self.coordinates = self._fill_coordinates()

    def own_actor(self, actor_id: int) -> ActorDescription:
        return next(
            actor
            for actor in self.game_state.actors
            if actor.team == self.own_team and actor.ident == actor_id
        )

    def enemy_actor_by_id(self, actor_id: int, team: str) -> ActorDescription:
        return next(
            actor
            for actor in self.game_state.actors
            if actor.team == team and actor.ident == actor_id
        )

    def actor_by_coordinates(self, coordinates: data.Coordinates) -> ActorDescription:
        return next(
            actor
            for actor in self.game_state.actors
            if actor.coordinates == coordinates
        )

    def enemy_actors_by_type(
        self, _type: str, team: str | None = None
    ) -> list[ActorDescription]:
        return [
            actor
            for actor in self.game_state.actors
            if (actor.team == team or team is None) and actor.type == _type
        ]

    def flag_by_coordinates(self, coordinates: data.Coordinates) -> FlagDescription:
        return next(
            flag for flag in self.game_state.flags if flag.coordinates == coordinates
        )

    def enemy_flag_by_team(self, team: str) -> FlagDescription:
        return next(flag for flag in self.game_state.flags if flag.team == team)

    def enemy_base(self, team: str) -> BaseDescription:
        return next(base for base in self.game_state.bases if base.team == team)

    def _fill_coordinates(self):
        coordinates = defaultdict(list)
        for actor in self.game_state.actors:
            coordinates[actor.coordinates].append(actor)
        for flag in self.game_state.flags:
            coordinates[flag.coordinates].append(flag)
        for base in self.game_state.bases:
            coordinates[base.coordinates].append(base)
        for wall in self.walls:
            coordinates[wall.coordinates].append(wall)
        return coordinates

    def _home_base(self) -> BaseDescription:
        return next(
            base for base in self.game_state.bases if base.team == self.own_team
        )

    def _own_flag(self) -> FlagDescription:
        return next(
            flag for flag in self.game_state.flags if flag.team == self.own_team
        )

    def _own_actors(self) -> list[ActorDescription]:
        return [
            actor for actor in self.game_state.actors if actor.team == self.own_team
        ]

    def _enemy_actors(self) -> list[ActorDescription]:
        return [
            actor for actor in self.game_state.actors if actor.team != self.own_team
        ]

    def _enemy_flags(self) -> list[FlagDescription]:
        return [flag for flag in self.game_state.flags if flag.team != self.own_team]

    def _walls(self) -> list[WallDescription]:
        return [wall for wall in self.game_state.walls]


"""
Basic interactions.
"""


def get_nearest_coordinates(
    origin: data.Coordinates,
    destinations: list[data.Coordinates],
    metric: metrics.Metric,
) -> data.Coordinates:
    result = []
    for destination in destinations:
        dist = metric.distance(origin, destination)
        result.append((dist, destination))
    result.sort(key=lambda x: x[0])
    return result[0][1]


T = TypeVar("T", ActorDescription, FlagDescription, WallDescription)


def get_nearest_object(
    origin_object: ActorDescription | FlagDescription | WallDescription,
    destination_objects: Sequence[T],
    metric: metrics.Metric,
) -> T:
    result = []
    for destination_object in destination_objects:
        dist = metric.distance(
            origin_object.coordinates, destination_object.coordinates
        )
        result.append((dist, destination_object))
    result.sort(key=lambda x: x[0])
    return result[0][1]


def nearest_enemy(
    object: ActorDescription | FlagDescription | WallDescription,
    team: str,
    game_state: StateResponse,
    metric: metrics.Metric,
) -> ActorDescription:
    """
    Find the nearest enemy from a given object.
    """
    all_actors = game_state.actors
    enemy_actors = [actor for actor in all_actors if team != actor.team]
    return get_nearest_object(
        origin_object=object, destination_objects=enemy_actors, metric=metric
    )


def nearest_enemy_flag(
    object: ActorDescription | FlagDescription | WallDescription,
    team: str,
    game_state: StateResponse,
    metric: metrics.Metric,
) -> FlagDescription:
    """
    Find the nearest enemy from a given object.
    """
    enemy_actors = [flag for flag in game_state.flags if team != flag.team]
    return get_nearest_object(
        origin_object=object, destination_objects=enemy_actors, metric=metric
    )
