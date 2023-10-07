from typing import Sequence, TypeVar

import ascifight.board.data as data
from ascifight.routers.states import (
    ActorDescription,
    FlagDescription,
    WallDescription,
)
from ascifight.board.actions import Directions
import ascifight.client_lib.metrics as asci_metrics
import ascifight.client_lib.object as asci_object


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


"""
Basic interactions.
"""


def get_nearest_coordinates(
    origin: data.Coordinates,
    destinations: list[data.Coordinates],
    metric: asci_metrics.Metric,
) -> data.Coordinates:
    """
    Calculate the nearest coordinates from a set of coordinates to an origin coordinate.
    """
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
    metric: asci_metrics.Metric,
) -> T:
    """
    Calculate the nearest board object from a list of board objects to an origin object.
    """
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
    objects: asci_object.Objects,
    metric: asci_metrics.Metric,
) -> ActorDescription:
    """
    Find the nearest enemy from a given object.
    """
    return get_nearest_object(
        origin_object=object, destination_objects=objects.enemy_actors, metric=metric
    )


def nearest_enemy_flag(
    object: ActorDescription | FlagDescription | WallDescription,
    objects: asci_object.Objects,
    metric: asci_metrics.Metric,
) -> FlagDescription:
    """
    Find the nearest enemy from a given object.
    """
    return get_nearest_object(
        origin_object=object, destination_objects=objects.enemy_flags, metric=metric
    )
