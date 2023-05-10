import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

import ascifight.config as config
import ascifight.globals as globals
import ascifight.board.data as data


class ActorDescription(BaseModel):
    type: str = Field(description="The type of the actor determining its capabilities.")
    team: str = Field(description="The name of the actor's team.")
    ident: int = Field(description="The identity number specific to the team.")
    flag: str | None = Field(
        description="If and which teams flag the actor is carrying."
    )
    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the actor."
    )


class FlagDescription(BaseModel):
    team: str = Field(description="The name of the flags's team.")
    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the flag."
    )


class BaseDescription(BaseModel):
    team: str = Field(description="The name of the base's team.")
    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the base."
    )


class StateResponse(BaseModel):
    teams: list[str] = Field(description="A list of all teams in the game.")
    actors: list[ActorDescription] = Field(
        description="A list of all actors in the game."
    )
    flags: list[FlagDescription] = Field(description="A list of all flags in the game.")
    bases: list[BaseDescription] = Field(description="A list of all bases in the game.")
    walls: list[data.Coordinates] = Field(
        description="A list of all walls in the game. Actors can not enter wall fields."
    )
    scores: dict[str, int] = Field(description="A dictionary of the current scores.")
    tick: int = Field(description="The last game tick.")
    time_of_next_execution: datetime.datetime = Field(
        description="The time of next execution."
    )


class TimingResponse(BaseModel):
    tick: int = Field(description="The last game tick.")
    time_to_next_execution: datetime.timedelta = Field(
        description="The time to next execution in seconds."
    )
    time_of_next_execution: datetime.datetime = Field(
        description="The time of next execution."
    )


class RulesResponse(BaseModel):
    map_size: int = Field(
        description="The length of the game board in x and y.",
    )
    max_ticks: int = Field(
        description="The maximum number of ticks the game will last.",
    )
    max_score: int = Field(
        description="The maximum score that will force the game to end.",
    )
    home_flag_required: bool = Field(
        description="Is the flag required to be at home to score?",
    )
    actor_properties: list[data.ActorProperty]


router = APIRouter(
    prefix="/states",
    tags=["states"],
)


@router.get("/game_state")
async def get_game_state() -> StateResponse:
    """Get the current state of the game including locations of all actors, flags, bases and walls."""
    return StateResponse(
        teams=[team.name for team in globals.my_game.board.teams],
        actors=[
            ActorDescription(
                type=actor.__class__.__name__,
                team=actor.team.name,
                ident=actor.ident,
                flag=actor.flag.team.name if actor.flag else None,
                coordinates=coordinates,
            )
            for actor, coordinates in globals.my_game.board.actors_coordinates.items()
        ],
        flags=[
            FlagDescription(team=flag.team.name, coordinates=coordinates)
            for flag, coordinates in globals.my_game.board.flags_coordinates.items()
        ],
        bases=[
            BaseDescription(team=base.team.name, coordinates=coordinates)
            for base, coordinates in globals.my_game.board.bases_coordinates.items()
        ],
        walls=list(globals.my_game.board.walls_coordinates),
        scores={team.name: score for team, score in globals.my_game.scores.items()},
        tick=globals.my_game.tick,
        time_of_next_execution=globals.time_of_next_execution,
    )


@router.get("/game_rules")
async def get_game_rules() -> RulesResponse:
    """Get the current rules and actor properties."""
    actor_properties = globals.my_game.board.get_actor_properties()
    return RulesResponse(
        map_size=config.config["game"]["map_size"],
        max_ticks=config.config["game"]["max_ticks"],
        max_score=config.config["game"]["max_score"],
        home_flag_required=config.config["game"]["home_flag_required"],
        actor_properties=actor_properties,
    )


@router.get("/timing")
async def get_timing() -> TimingResponse:
    """Get the current tick and time of next execution. If current tick is 0, game has not yet started."""
    return TimingResponse(
        tick=globals.my_game.tick,
        time_to_next_execution=globals.time_of_next_execution - datetime.datetime.now(),
        time_of_next_execution=globals.time_of_next_execution,
    )
