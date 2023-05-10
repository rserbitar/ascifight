import secrets
from typing import Annotated

from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path

import ascifight.config as config
import ascifight.globals as globals
import ascifight.game as game
import ascifight.board.computations as computations

security = HTTPBasic()


teams: dict[bytes, bytes] = {
    team["name"].encode("utf8"): team["password"].encode("utf8")
    for team in config.config["teams"]
}


def get_current_team(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    current_username_bytes = credentials.username.encode("utf8")

    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = b""
    if current_username_bytes in teams.keys():
        correct_password_bytes = teams[current_username_bytes]
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not is_correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


actor_annotation = Annotated[
    int,
    Path(
        title="Actor",
        description="The actor to act.",
        ge=0,
        le=len(config.config["game"]["actors"]) - 1,
    ),
]

direction_annotation = Annotated[
    computations.Directions,
    Query(
        title="Direction",
        description="The direction the actor should perform the action to.",
    ),
]

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)


@router.post("/move/{actor}")
async def move_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """Move an actor into a direction. Moving over your own flag return it to the base."""
    order = game.MoveOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Move order added."}


@router.post("/grabput/{actor}")
async def grabput_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """If the actor has a flag it puts it, even to another actor that can carry it. If it doesn't have a flag, it grabs it, even from another actor."""
    order = game.GrabPutOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Grabput order added."}


@router.post("/attack/{actor}")
async def attack_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """Only actors with the attack property can attack."""
    order = game.AttackOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Attack order added."}

@router.post("/destroy/{actor}")
async def destroy_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """Only actors with the destroy property can attack."""
    order = game.DestroyOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Destroy order added."}

@router.post("/build/{actor}")
async def build_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """Only actors with the build property can attack."""
    order = game.BuildOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Build order added."}


