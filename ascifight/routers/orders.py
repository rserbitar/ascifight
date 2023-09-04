from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

import ascifight.globals as globals
import ascifight.game as game
import ascifight.routers.router_utils as router_utils


class OrderResponse(BaseModel):
    message: str = Field(description="Order response message")


router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)


@router.post("/move/{actor}", status_code=202)
async def move_order(
    team: Annotated[str, Depends(router_utils.get_current_team)],
    actor: router_utils.actor_annotation,
    direction: router_utils.direction_annotation,
) -> OrderResponse:
    """With a move order you can move around any of your _actors_, by exactly one
    field in any non-diagonal direction.

    It is not allowed to step on fields:

    * **contain another actor**
    * **contain a base**
    * **contain a wall field**

    If an _actor_ moves over the flag of its own team, the flag is returned to its base!
    """
    order = game.MoveOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return OrderResponse(message="Move order added.")


@router.post("/grabput/{actor}", status_code=202)
async def grabput_order(
    team: Annotated[str, Depends(router_utils.get_current_team)],
    actor: router_utils.actor_annotation,
    direction: router_utils.direction_annotation,
) -> OrderResponse:
    """If an _actor_ does not have the flag, it can grab it with this order.
    Give it a direction from its current position and it will try to grab
    the _flag_ from the target field, even from another _actor_.

    If an _actor_ does have the flag it can put it into a target field. This target
    field can be empty or contain an _actor_, but not a wall.
    If the target field contains an _actor_ that can not carry the flag
    (_grab_ property is zero) this will not work. If an _actor_ puts a an enemy flag
    on its on base, you **capture** (sometimes the rule-set requires the own teams
    flag to be at their base to do so)! Depending on the rule set the capturing
    team gets points for capturing the flag.

    GrabPut actions only have a certain probability to work. If the _grab_ property
    of an _actor_ is smaller than 1, grabbing or putting might not always succeed.

    Only _actors_ with a non-zero _grab_ property can _grabput_.
    """
    order = game.GrabPutOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return OrderResponse(message="Grabput order added.")


@router.post("/attack/{actor}", status_code=202)
async def attack_order(
    team: Annotated[str, Depends(router_utils.get_current_team)],
    actor: router_utils.actor_annotation,
    direction: router_utils.direction_annotation,
) -> OrderResponse:
    """With attack orders you can force other actors, even your own, to respawn near
    their base. Just hit them and they are gone.

    Attack actions affect exactly one space in the direction of the attack. They
    only have a certain probability to work.
    If the _attack_ property of an _actor_ is smaller than 1, attacking might not
    succeed always.
    Depending on the rule-set killing other _actors_ will result in scoring points.

    Only _actors_ with a non-zero _attack_ property can _attack_."""
    order = game.AttackOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return OrderResponse(message="Attack order added.")


@router.post("/destroy/{actor}", status_code=202)
async def destroy_order(
    team: Annotated[str, Depends(router_utils.get_current_team)],
    actor: router_utils.actor_annotation,
    direction: router_utils.direction_annotation,
) -> OrderResponse:
    """Destroy orders you can remove those pesky walls. Just walk up to them and
    target the next wall with a destroy order.


    Destroy actions only have a certain probability to work. If the _destroy_
    property of an _actor_ is smaller than 1, destroying might not succeed always.

    Only _actors_ with a non-zero _destroy_ property can _destroy_."""
    order = game.DestroyOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return OrderResponse(message="Destroy order added.")


@router.post("/build/{actor}", status_code=202)
async def build_order(
    team: Annotated[str, Depends(router_utils.get_current_team)],
    actor: router_utils.actor_annotation,
    direction: router_utils.direction_annotation,
) -> OrderResponse:
    """Build orders can get you more walls where you want them. Walk next to the
    location where you want a wall and then start building.


    Build actions only have a certain probability to work. If the _build_ property
    of an _actor_ is smaller than 1, building might not succeed always.

    Only _actors_ with a non-zero _build_ property can _build_."""
    order = game.BuildOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return OrderResponse(message="Build order added.")
