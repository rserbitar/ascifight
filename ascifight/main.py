from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError, Field
import logging
import structlog
from structlog.contextvars import bind_contextvars

import datetime
import asyncio
import os

import game

# structlog.configure(
#     processors=[
#         structlog.contextvars.merge_contextvars,
#         structlog.processors.add_log_level,
#         structlog.processors.StackInfoRenderer(),
#         structlog.dev.set_exc_info,
#         structlog.processors.TimeStamper(),
#         structlog.dev.ConsoleRenderer(),
#     ],
#     context_class=dict,
#     wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
#     logger_factory=structlog.PrintLoggerFactory(),
#     cache_logger_on_first_use=False,
# )


timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False)
pre_chain = [
    # Add the log level and a timestamp to the event_dict if the log entry
    # is not from structlog.
    structlog.stdlib.add_log_level,
    # Add extra attributes of LogRecord objects to the event dictionary
    # so that values passed in the extra parameter of log methods pass
    # through to log output.
    structlog.stdlib.ExtraAdder(),
    timestamper,
]


logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "plain": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.contextvars.merge_contextvars,
                    structlog.processors.JSONRenderer(sort_keys=True),
                ],
                "foreign_pre_chain": pre_chain,
            },
            "colored": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.contextvars.merge_contextvars,
                    structlog.processors.add_log_level,
                    structlog.processors.StackInfoRenderer(),
                    structlog.dev.set_exc_info,
                    structlog.dev.ConsoleRenderer(colors=True),
                ],
                "foreign_pre_chain": pre_chain,
            },
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "colored",
            },
            "file": {
                "level": "DEBUG",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/game.log",
                "backupCount": 100,
                "formatter": "plain",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default", "file"],
                "level": "DEBUG",
                "propagate": True,
            },
        },
    }
)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

root_logger = logging.getLogger()

for handler in root_logger.handlers:
    if handler.__class__.__name__ == "RotatingFileHandler":
        handler.doRollover()

logger = structlog.get_logger()


WAIT_TIME = 5
PREGAME_WAIT = 3
LOGDIR = "logs"

SENTINEL = object()

app = FastAPI()
app.mount("/logs", StaticFiles(directory=LOGDIR), name="logs")

command_queue = asyncio.Queue()


class ActorDescriptions(BaseModel):
    team: str = Field(description="The name of the actor's team.")
    type: str = Field(decription="The type of the actor determining its capabilities.")
    ident: int = Field(description="The identity number specific to the team.")
    coordinates: game.Coordinates


class StateResponse(BaseModel):
    teams: list[str] = Field(
        description="A list of all teams in the game. This is also the order of flags and bases."
    )
    actors: list[ActorDescriptions] = Field(
        description="A list of all actors in the game."
    )
    flags: list[game.Coordinates] = Field(
        description="A list of all flags in the game. The flags are ordered according to the teams they belong to."
    )
    bases: list[game.Coordinates] = Field(
        description="A list of all bases in the game. The bases are ordered according to the teams they belong to."
    )
    walls: list[game.Coordinates] = Field(
        description="A list of all walls in the game. Actors can not enter wall fields."
    )
    scores: list[int] = Field(
        description="A list of the current scores. The scored are orderd according to the teams they belong to."
    )
    tick: int = Field(decription="The last game tick.")
    time_of_next_execution: datetime.datetime = Field(
        description="The time of next execution."
    )


class TimingResponse(BaseModel):
    tick: int = Field(decription="The last game tick.")
    time_of_next_execution: datetime.datetime = Field(
        description="The time of next execution."
    )


class ActorProperty(BaseModel):
    type: str
    grab: float = Field(
        description="The probability to successfully grab or put the flag. "
        "An actor with 0 can not carry the flag. Not even when it is given to it.",
    )
    attack: float = Field(
        description="The probability to successfully attack. An actor with 0 can not attack.",
    )


class PropertiesResponse(BaseModel):
    map_size: int = Field(
        default=game.MAP_SIZE, description="The length of the game board in x and y."
    )
    max_ticks: int = Field(
        default=game.MAX_TICKS,
        description="TThe maximum number of ticks the game will last.",
    )
    max_score: int = Field(
        default=game.MAX_SCORE,
        description="The maximum score that will force the game to end.",
    )
    actor_types: list[ActorProperty]


@app.post("/move_order")
async def move_order(order: game.MoveOrder):
    """Move an actor into a direction. Moving over your own flag return it to the base."""
    command_queue.put_nowait(order)
    return {"message": "Move order added."}


@app.post("/attack_order")
async def attack_order(order: game.AttackOrder):
    """Only actors with the attack property can attack."""
    command_queue.put_nowait(order)
    return {"message": "Attack order added."}


@app.post("/grabput_order")
async def grabput_order(order: game.GrabPutOrder):
    """If the actor has a flag it puts it, even to another actor that can carry it. If it doesnt have a flag, it grabs it, even from another actor."""
    command_queue.put_nowait(order)
    return {"message": "Grabput order added."}


@app.get("/state")
async def get_state() -> StateResponse:
    """Get the current state of the game including locations of all actors, flags, bases and walls."""
    return StateResponse(
        teams=mygame.teams,
        actors=[
            ActorDescriptions(
                team=actor.team.name,
                type=actor.type,
                ident=actor.ident,
                coordinates=coordinates,
            )
            for actor, coordinates in mygame.board.actors_coordinates.items()
        ],
        flags=list(mygame.board.flags_coordinates.values()),
        bases=list(mygame.board.bases_coordinates.values()),
        walls=list(mygame.board.walls_coordinates),
        scores=list(mygame.scores.values()),
        tick=mygame.tick,
        time_of_next_execution=mygame.time_of_next_execution,
    )


@app.get("/game_properties")
async def get_game_properties() -> PropertiesResponse:
    """Get the current rules and actor properties."""
    actor_types = [
        ActorProperty(type=actor.type, grab=actor.grab, attack=actor.attack)
        for actor in mygame.actors_of_team[mygame.teams[0]]
    ]
    return PropertiesResponse(actor_types=actor_types)


@app.get("/timeing")
async def get_timeing() -> TimingResponse:
    """Get the current tick and time of next execution."""
    return TimingResponse(
        tick=mygame.tick,
        time_of_next_execution=mygame.time_of_next_execution,
    )


@app.get("/logfiles")
async def get_logfiles() -> list[str]:
    """Get all log files accesible through /logs/[filename]"""
    return os.listdir(LOGDIR)


teams = [
    game.Team(name="S", password="1", number=0),
    game.Team(name="G", password="1", number=1),
    game.Team(name="M", password="1", number=2),
]

mygame = game.Game(
    teams=teams,
    pregame_wait=PREGAME_WAIT,
    board=game.Board(map_size=game.MAP_SIZE, walls=0),
    actors=game.InitialActorsList(actors=[game.Generalist]),
)


# game = Game(teams=teams, pregame_wait = PREGAME_WAIT,
#     board=Board(map_size=game.MAP_SIZE, walls=0),
#     actors=InitialActorsList(actors=[game.Generalist, game.Generalist, game.Generalist]),
# )

# game = Game(teams=teams, pregame_wait = PREGAME_WAIT,
#     board=Board(map_size=game.MAP_SIZE, walls=0),
#     actors=InitialActorsList(actors=[game.Runner, game.Attacker, game.Attacker]),
# )

# game = Game(teams=teams, pregame_wait = PREGAME_WAIT,
#     board=Board(map_size=game.MAP_SIZE, walls=10),
#     actors=InitialActorsList(actors=[game.Runner, game.Attacker, game.Attacker]),
# )

# game = Game(teams=teams, pregame_wait = PREGAME_WAIT,
#     board=Board(map_size=game.MAP_SIZE, walls=10),
#     actors=InitialActorsList(actors=[game.Runner, game.Attacker, game.Attacker, game.Blocker, game.Blocker]),
# )


async def routine():
    logger.info("Starting pre-game.")
    while mygame.pregame_wait > 0:
        await asyncio.sleep(1)
        mygame.pregame_wait -= 1

    logger.info("Initiating game.")
    mygame.initiate_game()

    while mygame.tick < game.MAX_TICKS and max(mygame.scores.values()) < game.MAX_SCORE:
        await command_queue.put(SENTINEL)

        commands = await get_all_queue_items(command_queue)

        bind_contextvars(tick=mygame.tick)
        os.system("cls" if os.name == "nt" else "clear")
        logger.info("Starting tick execution.")
        mygame.execute_gamestep(commands)

        print(mygame.scoreboard())
        print(mygame.board.image())

        logger.info("Waiting for game commands.")
        mygame.time_of_next_execution = datetime.datetime.now() + datetime.timedelta(
            0, WAIT_TIME
        )
        next_execution = mygame.time_of_next_execution
        logger.info(f"Time of next execution: {next_execution}")

        await asyncio.sleep(WAIT_TIME)


async def get_all_queue_items(queue):
    items = []
    item = await queue.get()
    while item is not SENTINEL:
        items.append(item)
        queue.task_done()
        item = await queue.get()
    queue.task_done()
    return items


async def ai_generator():
    await asyncio.sleep(1)
    while True:
        await asyncio.sleep(5)
        await command_queue.put(
            game.MoveOrder(team="Superteam", password="123", actor=0, direction="down")
        )
        await asyncio.sleep(5)
        await command_queue.put(
            game.MoveOrder(team="Superteam", password="123", actor=0, direction="right")
        )


@app.on_event("startup")
async def startup():
    asyncio.create_task(routine())
    # asyncio.create_task(ai_generator())
