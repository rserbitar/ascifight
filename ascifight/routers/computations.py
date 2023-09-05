from fastapi import APIRouter, Depends
from typing import Annotated

import ascifight.routers.router_utils as router_utils
import ascifight.board.data as data
import ascifight.board.computations as computations
import ascifight.globals as globals

router = APIRouter(
    prefix="/computations",
    tags=["computations"],
)


@router.post("/direction")
async def get_direction(
    origin: router_utils.origin_annotation, target: router_utils.target_annotation
) -> list[computations.Directions]:
    """Calculate the direction(s) to the target field from an origin field."""
    return computations.calc_target_coordinate_direction(origin, target)


@router.post("/distance")
async def get_distance(
    origin: router_utils.origin_annotation, target: router_utils.target_annotation
) -> int:
    """Calculate the distance in fields to the target field from an origin field."""
    return computations.distance(origin, target)


@router.post("/nearest_enemy")
async def get_nearest_enemy_coordinates(
    team: Annotated[str, Depends(router_utils.get_current_team)],
    actor: router_utils.actor_annotation,
) -> data.Coordinates:
    """Retrieve the coordinates of the nearest enemy of an actor. In case of
    multiple enemies with the same distance, result is chosen by internal order."""
    full_actor = globals.my_game.board.teams_actors[
        (globals.my_game.board.names_teams[team], actor)
    ]
    return computations.nearest_enemy_flag_coordinates(full_actor)


@router.post("/nearest_enemy_flag")
async def get_nearest_enemy_flag_coordinates(
    team: Annotated[str, Depends(router_utils.get_current_team)],
    actor: router_utils.actor_annotation,
) -> data.Coordinates:
    """Retrieve the coordinates of the nearest enemy flag to an actor. In case of
    multiple enemy flags with the same distance, result is chosen by internal order."""
    full_actor = globals.my_game.board.teams_actors[
        (globals.my_game.board.names_teams[team], actor)
    ]
    return computations.nearest_enemy_flag_coordinates(full_actor)
