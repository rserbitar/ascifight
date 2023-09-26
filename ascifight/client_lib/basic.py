import ascifight.board.data as data
import ascifight.routers.states as states
from ascifight.routers.states import StateResponse
from ascifight.board.computations import Directions


def destination_coordinates(
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


def destination_direction(
    origin: data.Coordinates,
    destination: data.Coordinates,
) -> list[Directions]:
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


def distance(
    origin: data.Coordinates,
    destination: data.Coordinates,
) -> int:
    x, y = distance_vector(origin, destination)
    return abs(x) + abs(y)


def distance_vector(
    origin: data.Coordinates,
    target: data.Coordinates,
) -> tuple[int, int]:
    x = target.x - origin.x
    y = target.y - origin.y
    return x, y


def nearest_enemy_coordinates(
    actor: states.ActorDescription, team: str, game_state: StateResponse
) -> data.Coordinates:
    all_actors = game_state.actors
    enemy_actors = [actor for actor in all_actors if team != actor.team]
    actor_coordinates = actor.coordinates
    result = []
    for enemy_actor in enemy_actors:
        enemy_coordinates = enemy_actor.coordinates
        dist = distance(
            actor_coordinates,
            enemy_coordinates,
        )
        result.append((dist, enemy_coordinates))
    result.sort(key=lambda x: x[0])
    return result[0][1]


def nearest_enemy_flag_coordinates(
    actor: states.ActorDescription, game_state: StateResponse
) -> data.Coordinates:
    flags = game_state.flags
    actor_coordinates = actor.coordinates
    result = []
    for flag in flags:
        if flag.team != actor.team:
            dist = distance(
                actor_coordinates,
                flag.coordinates,
            )
            result.append((dist, flag.coordinates))
    result.sort(key=lambda x: x[0])
    return result[0][1]
