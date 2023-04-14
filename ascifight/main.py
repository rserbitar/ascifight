import datetime
import logging, logging.config, logging.handlers
import asyncio
import os
import secrets
from typing import Annotated

from fastapi import FastAPI, Response, Depends, HTTPException, status, Query, Path
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from pydantic import BaseModel, Field
import structlog
from structlog.contextvars import bind_contextvars
import toml

import ascifight.config as config
import ascifight.globals as globals
import ascifight.game as game
import ascifight.board_data as board_data
import ascifight.board_computations as board_computations
import ascifight.draw as draw
import ascifight.util as util
import ascifight.game_loop as game_loop


try:
    os.mkdir(config.config["server"]["log_dir"])
except FileExistsError:
    pass

logging.config.dictConfig(util.log_config_dict)


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        util.time_stamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

root_logger = logging.getLogger()
logger = structlog.get_logger()


tags_metadata = [
    {
        "name": "orders",
        "description": "Operations to give orders to your actors.",
    },
    {
        "name": "states",
        "description": "Operations to get state information about the game.",
    },
    {
        "name": "logistics",
        "description": "Operations to provide quality of life support.",
    },
]


class ActorDescription(BaseModel):
    type: str = Field(description="The type of the actor determining its capabilities.")
    team: str = Field(description="The name of the actor's team.")
    ident: int = Field(description="The identity number specific to the team.")
    flag: str | None = Field(
        description="If and which teams flag the actor is carrying."
    )
    coordinates: board_data.Coordinates = Field(
        description="The current coordinates fo the actor."
    )


class FlagDescription(BaseModel):
    team: str = Field(description="The name of the flags's team.")
    coordinates: board_data.Coordinates = Field(
        description="The current coordinates fo the flag."
    )


class BaseDescription(BaseModel):
    team: str = Field(description="The name of the base's team.")
    coordinates: board_data.Coordinates = Field(
        description="The current coordinates fo the base."
    )


class StateResponse(BaseModel):
    teams: list[str] = Field(description="A list of all teams in the game.")
    actors: list[ActorDescription] = Field(
        description="A list of all actors in the game."
    )
    flags: list[FlagDescription] = Field(description="A list of all flags in the game.")
    bases: list[BaseDescription] = Field(description="A list of all bases in the game.")
    walls: list[board_data.Coordinates] = Field(
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
    actor_properties: list[board_data.ActorProperty]


app = FastAPI(
    openapi_tags=tags_metadata,
    title="A Social, Community Increasing - Fight",
    description=util.api_description,
    version="0.1",
    contact={
        "name": "Ralf Kelzenberg",
        "url": "http://vodafone.com",
        "email": "Ralf.Kelzenberg@vodafone.com",
    },
)
app.mount(
    "/logs", StaticFiles(directory=config.config["server"]["log_dir"]), name="logs"
)


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
    board_computations.Directions,
    Query(
        title="Direction",
        description="The direction the actor should perform the action to.",
    ),
]


@app.post(
    "/move_order/{actor}",
    tags=["orders"],
)
async def move_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """Move an actor into a direction. Moving over your own flag return it to the base."""
    order = game.MoveOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Move order added."}


@app.post(
    "/attack_order/{actor}",
    tags=["orders"],
)
async def attack_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """Only actors with the attack property can attack."""
    order = game.AttackOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Attack order added."}


@app.post(
    "/grabput_order/{actor}",
    tags=["orders"],
)
async def grabput_order(
    team: Annotated[str, Depends(get_current_team)],
    actor: actor_annotation,
    direction: direction_annotation,
) -> dict[str, str]:
    """If the actor has a flag it puts it, even to another actor that can carry it. If it doesn't have a flag, it grabs it, even from another actor."""
    order = game.GrabPutOrder(team=team, actor=actor, direction=direction)
    globals.command_queue.put_nowait(order)
    return {"message": "Grabput order added."}


@app.get("/game_state", tags=["states"])
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


@app.get("/game_rules", tags=["states"])
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


@app.get("/timing", tags=["states"])
async def get_timing() -> TimingResponse:
    """Get the current tick and time of next execution."""
    return TimingResponse(
        tick=globals.my_game.tick,
        time_to_next_execution=globals.time_of_next_execution - datetime.datetime.now(),
        time_of_next_execution=globals.time_of_next_execution,
    )


@app.get("/game_start", tags=["states"])
async def get_game_start() -> int:
    """Return the seconds till the game will start."""
    return config.config["server"]["pre_game_wait"]


@app.get("/log_files", tags=["logistics"])
async def get_log_files() -> list[str]:
    """Get all log files accessible through /logs/[filename]"""
    return os.listdir(config.config["server"]["log_dir"])


@app.get(
    "/image",
    tags=["logistics"],
    # Set what the media type will be in the autogenerated OpenAPI specification.
    # fastapi.tiangolo.com/advanced/additional-responses/#additional-media-types-for-the-main-response
    responses={200: {"content": {"image/png": {}}}},
    # Prevent FastAPI from adding "application/json" as an additional
    # response media type in the autogenerated OpenAPI specification.
    # https://github.com/tiangolo/fastapi/issues/3258
    response_class=Response,
)
def get_image() -> Response:
    actors = [
        draw.Icon(
            name=actor.__class__.__name__[0] + str(actor.ident),
            coordinates=coordinates,
            color=util.color_names[actor.team.number],
        )
        for actor, coordinates in globals.my_game.board.actors_coordinates.items()
    ]
    bases = [
        draw.Icon(
            name=util.base_icon,
            coordinates=coordinates,
            color=util.color_names[base.team.number],
        )
        for base, coordinates in globals.my_game.board.bases_coordinates.items()
    ]
    walls = [
        draw.Icon(
            name=util.wall_icon,
            coordinates=coordinates,
            color="white",
        )
        for coordinates in globals.my_game.board.walls_coordinates
    ]
    flags = [
        draw.Icon(
            name=util.flag_icon,
            coordinates=coordinates,
            color=util.color_names[flag.team.number],
        )
        for flag, coordinates in globals.my_game.board.flags_coordinates.items()
    ]
    image = draw.draw_map(actors + bases + walls, flags)
    # media_type here sets the media type of the actual response sent to the client.
    return Response(content=image, media_type="image/png")


@app.get("/status")
async def read_index():
    return FileResponse("templates/index.html")


@app.on_event("startup")
async def startup():
    pass
    asyncio.create_task(game_loop.routine())
    asyncio.create_task(game_loop.ai_generator())
