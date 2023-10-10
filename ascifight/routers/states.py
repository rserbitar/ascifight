import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

import ascifight.config as config
import ascifight.game as asci_game
import ascifight.globals as globals
import ascifight.board.data as data
import ascifight.util as util
import ascifight.board.actions as asci_actions


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

    def __eq__(self, other) -> bool:
        return self.ident == other.ident and self.team == other.team


class FlagDescription(BaseModel):
    """A flag that can be grabbed and put."""

    team: str = Field(description="The name of the flags's team.")
    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the flag."
    )

    def __eq__(self, other) -> bool:
        return self.team == other.team


class ActionDescription(BaseModel):
    type: str = Field(description="The name of the action.")
    actor: ActorDescription = Field(description="The actor performing the action.")
    destination: data.Coordinates = Field(
        description="The coordinates to which the actions where performed."
    )
    target: ActorDescription | None = Field(
        None, description="The actor that was target of the action."
    )
    origin: data.Coordinates | None = Field(
        None, description="The original coordinates in case of a MoveAction."
    )
    flag: FlagDescription | None = Field(
        None,
        description="The team name of the flag if a flag was involved in the action.",
    )


class BoardObjectDescription(BaseModel):
    """An object located on the board."""

    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the object."
    )


class BaseDescription(BoardObjectDescription):
    """A base that can hold or cap a flag."""

    team: str = Field(description="The name of the base's team.")
    coordinates: data.Coordinates = Field(
        description="The current coordinates fo the base."
    )


class WallDescription(BoardObjectDescription):
    """A wall that can not be moved through. Can be built and destroyed"""

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
    walls: list[WallDescription] = Field(
        description="A list of all walls in the game. Actors can not enter wall fields."
    )
    scores: dict[str, int] = Field(description="A dictionary of the current scores.")
    tick: int = Field(description="The last game tick.")
    time_of_next_execution: datetime.datetime = Field(
        description="The time of next execution."
    )


class CurrentActionsResponse(BaseModel):
    current_actions: list[ActionDescription] = Field(
        description="A list of all successfully performed actions in the current tick."
    )


class AllActionsResponse(BaseModel):
    all_actions: dict[int, list[ActionDescription]] = Field(
        description="A dictionary with each past tick int he game as key and a list of"
        "all successfully performed actions as value."
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
    return serialize_state(globals.my_game, globals.time_of_next_execution)


@router.get("/current_actions")
async def get_current_actions() -> CurrentActionsResponse:
    """
    Returns all actions that have been performed in the current tick.
    This includes only successful actions. Actions that have been tried but
    have not been performed due to various reasons are not shown."""
    return CurrentActionsResponse(
        current_actions=serialize_actions(globals.my_game.log[globals.my_game.tick])
    )


@router.get("/all_actions")
async def get_all_actions() -> AllActionsResponse:
    """
    Returns all actions that have been performed in the current tick.
    This includes only successful actions. Actions that have been tried but
    have not been performed due to various reasons are not shown."""
    return AllActionsResponse(all_actions=serialize_all_actions(globals.my_game.log))


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


def serialize_actor(actor) -> ActorDescription:
    return ActorDescription(
        type=actor.__class__.__name__,
        team=actor.team.name,
        ident=actor.ident,
        flag=actor.flag.team.name if actor.flag else None,
        coordinates=actor.coordinates,
    )


def serialize_flag(flag) -> FlagDescription:
    return FlagDescription(
        team=flag.team.name,
        coordinates=flag.coordinates,
    )


def serialize_actions(actions: list[asci_actions.Action]) -> list[ActionDescription]:
    result: list[ActionDescription] = []
    for action in actions:
        _type = action.__class__.__name__
        actor = serialize_actor(action.actor)
        destination = action.destination
        origin = None
        flag = None
        target = None
        match action:
            case asci_actions.MoveAction():
                origin = action.origin
            case asci_actions.BuildAction():
                pass
            case asci_actions.DestroyAction():
                pass
            case asci_actions.AttackAction():
                target = serialize_actor(action.target)
            case asci_actions.GrabAction():
                target = serialize_actor(action.target)
                flag = serialize_flag(action.flag)
            case asci_actions.PutAction():
                target = serialize_actor(action.target)
                flag = serialize_flag(action.flag)
        serialized_action = ActionDescription(
            type=_type,
            actor=actor,
            destination=destination,
            origin=origin,
            flag=flag,
            target=target,
        )
        result.append(serialized_action)
    return result


def serialize_all_actions(
    log: dict[int, list[asci_actions.Action]]
) -> dict[int, list[ActionDescription]]:
    result: dict[int, list[ActionDescription]] = {}
    for tick, actions in log.items():
        result[tick] = serialize_actions(actions)
    return result


def serialize_state(
    game: asci_game.Game, time_of_next_execution: datetime.datetime
) -> StateResponse:
    return StateResponse(
        teams=[team.name for team in game.board.teams],
        actors=[
            ActorDescription(
                type=actor.__class__.__name__,
                team=actor.team.name,
                ident=actor.ident,
                flag=actor.flag.team.name if actor.flag else None,
                coordinates=coordinates,
            )
            for actor, coordinates in game.board.actors_coordinates.items()
        ],
        flags=[
            FlagDescription(team=flag.team.name, coordinates=coordinates)
            for flag, coordinates in game.board.flags_coordinates.items()
        ],
        bases=[
            BaseDescription(team=base.team.name, coordinates=coordinates)
            for base, coordinates in game.board.bases_coordinates.items()
        ],
        walls=[
            WallDescription(coordinates=coordinates)
            for coordinates in game.board.walls_coordinates
        ],
        scores={team.name: score for team, score in game.scores.items()},
        tick=game.tick,
        time_of_next_execution=time_of_next_execution,
    )
