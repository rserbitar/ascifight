import datetime
import logging, logging.config, logging.handlers
import asyncio
import os
import importlib

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import structlog
from structlog.contextvars import bind_contextvars
import toml

import ascifight.game as game
import ascifight.board_data as board_data
import ascifight.board_actions as board_actions
import ascifight.draw as draw
import ascifight.util as util

with open("config.toml", mode="r") as fp:
    config = toml.load(fp)
try:
    os.mkdir(config["server"]["log_dir"])
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
_logger = structlog.get_logger()


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


class StateResponse(BaseModel):
    teams: list[str] = Field(
        description="A list of all teams in the game. This is also the order of flags and bases."
    )
    actors: list[ActorDescription] = Field(
        description="A list of all actors in the game."
    )
    flags: list[board_data.Coordinates] = Field(
        description="A list of all flags in the game. The flags are ordered according to the teams they belong to."
    )
    bases: list[board_data.Coordinates] = Field(
        description="A list of all bases in the game. The bases are ordered according to the teams they belong to."
    )
    walls: list[board_data.Coordinates] = Field(
        description="A list of all walls in the game. Actors can not enter wall fields."
    )
    scores: list[int] = Field(
        description="A list of the current scores. The scored are ordered according to the teams they belong to."
    )
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
app.mount("/logs", StaticFiles(directory=config["server"]["log_dir"]), name="logs")

SENTINEL = object()
time_to_next_execution: datetime.timedelta
time_of_next_execution: datetime.datetime
pre_game_wait: int
my_game: game.Game
command_queue: asyncio.Queue[game.Order | object] = asyncio.Queue()


@app.post("/move_order", tags=["orders"])
async def move_order(order: game.MoveOrder) -> dict[str, str]:
    """Move an actor into a direction. Moving over your own flag return it to the base."""
    command_queue.put_nowait(order)
    return {"message": "Move order added."}


@app.post("/attack_order", tags=["orders"])
async def attack_order(order: game.AttackOrder) -> dict[str, str]:
    """Only actors with the attack property can attack."""
    command_queue.put_nowait(order)
    return {"message": "Attack order added."}


@app.post("/grabput_order", tags=["orders"])
async def grabput_order(order: game.GrabPutOrder) -> dict[str, str]:
    """If the actor has a flag it puts it, even to another actor that can carry it. If it doesn't have a flag, it grabs it, even from another actor."""
    command_queue.put_nowait(order)
    return {"message": "Grabput order added."}


@app.get("/game_state", tags=["states"])
async def get_game_state() -> StateResponse:
    """Get the current state of the game including locations of all actors, flags, bases and walls."""
    return StateResponse(
        teams=[team.name for team in my_game.board.teams],
        actors=[
            ActorDescription(
                type=actor.__class__.__name__,
                team=actor.team.name,
                ident=actor.ident,
                flag=actor.flag.team.name if actor.flag else None,
                coordinates=coordinates,
            )
            for actor, coordinates in my_game.board.actors_coordinates.items()
        ],
        flags=list(my_game.board.flags_coordinates.values()),
        bases=list(my_game.board.bases_coordinates.values()),
        walls=list(my_game.board.walls_coordinates),
        scores=list(my_game.scores.values()),
        tick=my_game.tick,
        time_of_next_execution=time_of_next_execution,
    )


@app.get("/game_rules", tags=["states"])
async def get_game_rules() -> RulesResponse:
    """Get the current rules and actor properties."""
    actor_properties = my_game.board.get_actor_properties()
    return RulesResponse(
        map_size=config["game"]["map_size"],
        max_ticks=config["game"]["max_ticks"],
        max_score=config["game"]["max_score"],
        home_flag_required=config["game"]["home_flag_required"],
        actor_properties=actor_properties,
    )


@app.get("/timing", tags=["states"])
async def get_timing() -> TimingResponse:
    """Get the current tick and time of next execution."""
    return TimingResponse(
        tick=my_game.tick,
        time_to_next_execution=time_of_next_execution - datetime.datetime.now(),
        time_of_next_execution=time_of_next_execution,
    )


@app.get("/game_start", tags=["states"])
async def get_game_start() -> int:
    """Return the seconds till the game will start."""
    return pre_game_wait


@app.get("/log_files", tags=["logistics"])
async def get_log_files() -> list[str]:
    """Get all log files accessible through /logs/[filename]"""
    return os.listdir(config["server"]["log_dir"])


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
        for actor, coordinates in my_game.board.actors_coordinates.items()
    ]
    bases = [
        draw.Icon(
            name=util.base_icon,
            coordinates=coordinates,
            color=util.color_names[base.team.number],
        )
        for base, coordinates in my_game.board.bases_coordinates.items()
    ]
    walls = [
        draw.Icon(
            name=util.wall_icon,
            coordinates=coordinates,
            color="white",
        )
        for coordinates in my_game.board.walls_coordinates
    ]
    flags = [
        draw.Icon(
            name=util.flag_icon,
            coordinates=coordinates,
            color=util.color_names[flag.team.number],
        )
        for flag, coordinates in my_game.board.flags_coordinates.items()
    ]
    image = draw.draw_map(actors + bases + walls, flags)
    # media_type here sets the media type of the actual response sent to the client.
    return Response(content=image, media_type="image/png")


async def routine():
    while True:
        await single_game()


async def single_game() -> None:
    global my_game
    global pre_game_wait
    global time_of_next_execution
    global time_to_next_execution
    global config

    with open("config.toml", mode="r") as fp:
        config = toml.load(fp)
    importlib.reload(game)

    pre_game_wait = config["server"]["pre_game_wait"]
    for handler in root_logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.doRollover()
    my_game = game.Game()

    _logger.info("Initiating game.")
    my_game.initiate_game()

    _logger.info("Starting pre-game.")
    while pre_game_wait > 0:
        await asyncio.sleep(1)
        pre_game_wait -= 1

    while not my_game.check_game_end():
        await command_queue.put(SENTINEL)

        commands = await get_all_queue_items(command_queue)

        bind_contextvars(tick=my_game.tick)
        os.system("cls" if os.name == "nt" else "clear")

        print(my_game.scoreboard())
        print(my_game.board.image())

        _logger.info("Starting tick execution.")
        my_game.execute_game_step(commands)

        _logger.info("Waiting for game commands.")
        time_of_next_execution = datetime.datetime.now() + datetime.timedelta(
            0, config["server"]["tick_wait_time"]
        )
        _logger.info(f"Time of next execution: {time_of_next_execution}")

        await asyncio.sleep(config["server"]["tick_wait_time"])
    my_game.end_game()
    os.system("cls" if os.name == "nt" else "clear")
    print(my_game.scoreboard())
    print(my_game.board.image())


async def get_all_queue_items(
    queue: asyncio.Queue[game.Order | object],
) -> list[game.Order]:
    items: list[game.Order] = []
    item = await queue.get()
    while item is not SENTINEL:
        items.append(item)  # type: ignore
        queue.task_done()
        item = await queue.get()
    queue.task_done()
    return items


async def ai_generator():
    await asyncio.sleep(1)
    while True:
        await asyncio.sleep(5)
        await command_queue.put(
            game.MoveOrder(
                team="Team 1",
                password="1",
                actor=0,
                direction=board_actions.Directions.down,
            )
        )
        await asyncio.sleep(5)
        await command_queue.put(
            game.MoveOrder(
                team="Team 2",
                password="2",
                actor=0,
                direction=board_actions.Directions.right,
            )
        )


@app.on_event("startup")
async def startup():
    asyncio.create_task(routine())
    asyncio.create_task(ai_generator())
