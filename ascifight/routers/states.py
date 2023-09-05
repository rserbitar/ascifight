import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

import ascifight.config as config
import ascifight.globals as globals
import ascifight.board.data as data
import ascifight.util as util


class ActorDescription(BaseModel):
    """An actor able to execute orders."""

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
    """A flag that can be grabbed and put."""

    team: str = Field(description="The name of the flags's team.")
    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the flag."
    )


class BaseDescription(BaseModel):
    """A base that can hold or cap a flag."""

    team: str = Field(description="The name of the base's team.")
    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the base."
    )


class Scores(BaseModel):
    """Scores describing who is currently winning the game."""

    team: str = Field(description="The name of the team.")
    score: int = Field(description="The scores of the current game.")
    color: str = Field(description="The color of the team.")


class AllScoresResponse(BaseModel):
    """The total scores of all games."""

    scores: list[Scores] = Field(description="The scores of the current game.")
    overall_scores: list[Scores] = Field(
        description="The current overall scores of all games."
    )


class StateResponse(BaseModel):
    """All entities of a game including their coordinates."""

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
    """Various current timing data."""

    tick: int = Field(description="The last game tick.")
    time_to_next_execution: float = Field(
        description="The time to next execution in seconds."
    )
    time_of_next_execution: datetime.datetime = Field(
        description="The time of next execution."
    )


class RulesResponse(BaseModel):
    """The current rules affecting the current game."""

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
    capture_score: int = Field(
        description="The number of points a team that captures a flag gets.",
    )
    kill_score: int = Field(
        description="The number of points a team that kills an actor gets.",
    )
    winning_bonus: int = Field(
        description=(
            "The additional bonus a team that is winning a game gets for overall "
            "scores."
        ),
    )
    actor_properties: list[data.ActorProperty] = Field(
        description=(
            "A list of actors and their properties describing which orders "
            "they can perform with what probability."
        ),
    )


router = APIRouter(
    prefix="/states",
    tags=["states"],
)


@router.get("/game_state")
async def get_game_state() -> StateResponse:
    """Get the current state of the game including locations of all actors,
    flags, bases and walls."""
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


@router.get("/scores")
async def get_scores() -> AllScoresResponse:
    """Get the scores of the current game as well as all games in total."""
    return AllScoresResponse(
        scores=[
            Scores(team=team.name, score=score, color=util.color_names[team.number])
            for team, score in globals.my_game.scores.items()
        ],
        overall_scores=[
            Scores(team=team.name, score=score, color=util.color_names[team.number])
            for team, score in globals.my_game.overall_scores.items()
        ],
    )


@router.get("/game_rules")
async def get_game_rules() -> RulesResponse:
    """This section is static per game and returns what each actor can do,
    if the flag needs to be at home to score, what the maximum score or
    tick number is and other static information."""
    actor_properties = globals.my_game.board.get_actor_properties()
    return RulesResponse(
        map_size=config.config["game"]["map_size"],
        max_ticks=config.config["game"]["max_ticks"],
        max_score=config.config["game"]["max_score"],
        capture_score=config.config["game"]["capture_score"],
        kill_score=config.config["game"]["kill_score"],
        winning_bonus=config.config["game"]["winning_bonus"],
        home_flag_required=config.config["game"]["home_flag_required"],
        actor_properties=actor_properties,
    )


@router.get("/timing")
async def get_timing() -> TimingResponse:
    """
    Returns the current tick and when the next tick executes both on absolute time
    and time-deltas. If current tick is 0, game has not yet started.

    This is more lightweight than the _Game State_ an can be queried
    often. Get the current tick and time of next execution."""
    return TimingResponse(
        tick=globals.my_game.tick,
        time_to_next_execution=(
            globals.time_of_next_execution - datetime.datetime.now()
        ).total_seconds(),
        time_of_next_execution=globals.time_of_next_execution,
    )
