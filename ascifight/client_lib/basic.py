import functools
from typing import Callable

import ascifight.board.data as data
import ascifight.routers.states as states
from ascifight.routers.states import (
    BaseDescription,
    StateResponse,
    ActorDescription,
    FlagDescription,
)
from ascifight.board.computations import Directions

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


def destination_direction(
    origin: data.Coordinates,
    destination: data.Coordinates,
) -> list[Directions]:
    """
    Calculate direction given origin coordinates and destination coordinates.
    """
    direction = [Directions.up]

    x, y = distance_vector(origin, destination)

    if abs(x) == abs(y):
        if x > 0 and y > 0:
            direction = [Directions.up, Directions.right]
        elif x > 0 and y < 0:
            direction = [Directions.right, Directions.down]
        elif x < 0 and y > 0:
            direction = [Directions.left, Directions.up]
        elif x < 0 and y < 0:
            direction = [Directions.down, Directions.left]

    elif abs(y) > abs(x):
        if y > 0:
            direction = [Directions.up]
        else:
            direction = [Directions.down]
    else:
        if x > 0:
            direction = [Directions.right]
        else:
            direction = [Directions.left]

    return direction


"""Basic Metrics"""


def distance(
    origin: data.Coordinates,
    destination: data.Coordinates,
    game_state: StateResponse | None = None,
) -> int:
    """
    Calculate the distance in steps between origin and destination coordinates.
    """
    x, y = distance_vector(origin, destination)
    return abs(x) + abs(y)


def distance_vector(
    origin: data.Coordinates,
    destination: data.Coordinates,
) -> tuple[int, int]:
    """
    Calculate the distance vector between origin and destination coordinates.
    """
    x = destination.x - origin.x
    y = destination.y - origin.y
    return x, y


class Objects:
    """
    Basic objects.
    """

    def __init__(self, game_state: StateResponse, own_team: str):
        self.game_state = game_state
        self.own_team = own_team

    @functools.cache
    def home_base(self) -> BaseDescription:
        return [base for base in self.game_state.bases if base.team == self.own_team][0]

    @functools.cache
    def own_flag(self) -> FlagDescription:
        return [flag for flag in self.game_state.flags if flag.team == self.own_team][0]

    @functools.cache
    def own_actor(self, actor_id: int) -> ActorDescription:
        return [
            actor
            for actor in self.game_state.actors
            if actor.team == self.own_team and actor.ident == actor_id
        ][0]

    @functools.cache
    def enemy_actor(self, actor_id: int, team: str) -> ActorDescription:
        return [
            actor
            for actor in self.game_state.actors
            if actor.team == team and actor.ident == actor_id
        ][0]

    @functools.cache
    def own_actors(self) -> list[ActorDescription]:
        return [
            actor for actor in self.game_state.actors if actor.team == self.own_team
        ]

    @functools.cache
    def enemy_actors(self) -> list[ActorDescription]:
        return [
            actor for actor in self.game_state.actors if actor.team != self.own_team
        ]

    @functools.cache
    def walls(self) -> list[data.Coordinates]:
        return self.game_state.walls


"""
Basic interactions.
"""


def get_nearest_coordinates(
    origin: data.Coordinates,
    destinations: list[data.Coordinates],
    metric: Callable[[data.Coordinates, data.Coordinates, StateResponse], int],
    game_state: StateResponse,
) -> data.Coordinates:
    result = []
    for destination in destinations:
        dist = metric(origin, destination, game_state)
        result.append((dist, destination))
    result.sort(key=lambda x: x[0])
    return result[0][1]


def nearest_enemy_coordinates(
    actor: states.ActorDescription,
    game_state: StateResponse,
    metric: Callable[
        [data.Coordinates, data.Coordinates, StateResponse], int
    ] = distance,
) -> data.Coordinates:
    """
    Find the nearest enemy from a given actor.
    """
    team = actor.team
    all_actors = game_state.actors
    enemy_actor_coordinates = [
        actor.coordinates for actor in all_actors if team != actor.team
    ]
    actor_coordinates = actor.coordinates
    return get_nearest_coordinates(
        origin=actor_coordinates,
        destinations=enemy_actor_coordinates,
        metric=metric,
        game_state=game_state,
    )


def nearest_enemy_flag_coordinates(
    actor: states.ActorDescription,
    game_state: StateResponse,
    metric: Callable[
        [data.Coordinates, data.Coordinates, StateResponse], int
    ] = distance,
) -> data.Coordinates:
    """
    Find the nearest enemy flag from a given actor.
    """

    enemy_flag_coordinates = [
        flag.coordinates for flag in game_state.flags if flag.team != actor.team
    ]
    actor_coordinates = actor.coordinates
    return get_nearest_coordinates(
        origin=actor_coordinates,
        destinations=enemy_flag_coordinates,
        metric=metric,
        game_state=game_state,
    )
