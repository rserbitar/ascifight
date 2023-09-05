import enum
from itertools import chain

import ascifight.board.data as data
import ascifight.globals as globals


class Directions(str, enum.Enum):
    left = "left"
    right = "right"
    down = "down"
    up = "up"


def calc_target_coordinates(
    coordinates: data.Coordinates,
    direction: Directions,
    map_size: int,
) -> data.Coordinates:
    new_coordinates = data.Coordinates(x=coordinates.x, y=coordinates.y)
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
    origin: data.Coordinates,
    target: data.Coordinates,
) -> list[Directions]:
    direction = [Directions.up]

    x, y = distance_vector(origin, target)

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


def distance(
    origin: data.Coordinates,
    target: data.Coordinates,
) -> int:
    x, y = distance_vector(origin, target)
    return abs(x) + abs(y)


def distance_vector(
    origin: data.Coordinates,
    target: data.Coordinates,
) -> tuple[int, int]:
    x = target.x - origin.x
    y = target.y - origin.y
    return x, y


def nearest_enemy_coordinates(actor: data.Actor) -> data.Coordinates:
    board = globals.my_game.board
    all_actors = board.actors_of_team
    enemy_actors = chain.from_iterable(
        [actors for team, actors in all_actors.items() if team != actor.team]
    )
    actor_coordinates = board.actors_coordinates[actor]
    result = []
    for enemy_actor in enemy_actors:
        enemy_coordinates = board.actors_coordinates[enemy_actor]
        dist = distance(
            actor_coordinates,
            enemy_coordinates,
        )
        result.append((dist, enemy_coordinates))
    result.sort(key=lambda x: x[0])
    return result[0][1]


def nearest_enemy_flag_coordinates(actor: data.Actor) -> data.Coordinates:
    board = globals.my_game.board
    flags = board.flags_coordinates
    actor_coordinates = board.actors_coordinates[actor]
    result = []
    for flag, coordinates in flags.items():
        if flag.team != actor.team:
            dist = distance(
                actor_coordinates,
                coordinates,
            )
            result.append((dist, coordinates))
    result.sort(key=lambda x: x[0])
    return result[0][1]
