from pydantic import ValidationError
import toml
import structlog

import random
import enum
import math

import ascifight.board_data as board_data


class Directions(str, enum.Enum):
    left = "left"
    right = "right"
    down = "down"
    up = "up"


def calc_target_coordinates(
    coordinates: board_data.Coordinates,
    direction: Directions,
    map_size: int,
) -> board_data.Coordinates:
    new_coordinates = board_data.Coordinates(x=coordinates.x, y=coordinates.y)
    match direction:
        case direction.right:
            new_coordinates.x = min(coordinates.x + 1, map_size - 1)
        case direction.left:
            new_coordinates.x = max(coordinates.x - 1, 0)
        case direction.up:
            new_coordinates.y = min(coordinates.y + 1, map_size - 1)
        case direction.down:
            new_coordinates.y = max(coordinates.y - 1, 0)
    return new_coordinates


def calc_target_coordinate_direction(
    origin: board_data.Coordinates,
    target: board_data.Coordinates,
) -> list[Directions]:
    direction = [Directions.up]

    x, y = distance_vector(origin, target)

    if abs(x) == abs(y):
        if x > 0 and y > 0:
            direction = [Directions.up, Directions.right]
        elif x > 0 and y < 0:
            direction = [Directions.right, Directions.down]
        if x < 0 and y > 0:
            direction = [Directions.left, Directions.up]
        elif x < 0 and y < 0:
            direction = [Directions.down, Directions.left]

    elif y > 0:
        if abs(y) > abs(x):
            direction = [Directions.up]
        else:
            if x > 0:
                direction = [Directions.right]
            else:
                direction = [Directions.left]
    else:
        if abs(y) > abs(x):
            direction = [Directions.down]
        else:
            if x > 0:
                direction = [Directions.right]
            else:
                direction = [Directions.left]

    return direction


def distance(
    origin: board_data.Coordinates,
    target: board_data.Coordinates,
) -> int:
    x, y = distance_vector(origin, target)
    return abs(x) + abs(y)


def distance_vector(
    origin: board_data.Coordinates,
    target: board_data.Coordinates,
) -> tuple[int, int]:
    x = target.x - origin.x
    y = target.y - origin.y
    return x, y
