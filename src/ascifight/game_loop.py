import asyncio
import importlib
import datetime
import os
import logging
import logging.handlers

import structlog
from structlog.contextvars import bind_contextvars

import ascifight.config as config
import ascifight.globals as globals
import ascifight.game as game

root_logger = logging.getLogger()
logger = structlog.get_logger()
SENTINEL = object()


async def routine():
    while True:
        await single_game()


async def single_game() -> None:
    importlib.reload(config)
    importlib.reload(game)

    pre_game_wait = config.config["server"]["pre_game_wait"]
    for handler in root_logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.doRollover()
    globals.my_game = game.Game()

    logger.info("Initiating game.")
    globals.my_game.initiate_game()

    logger.info("Starting pre-game.")
    globals.time_to_next_execution = pre_game_wait
    globals.time_of_next_execution = datetime.datetime.now() + datetime.timedelta(
        seconds=pre_game_wait
    )
    await asyncio.sleep(pre_game_wait)

    while not globals.my_game.check_game_end():
        await globals.command_queue.put(SENTINEL)

        commands = await get_all_queue_items(globals.command_queue)

        bind_contextvars(tick=globals.my_game.tick)
        if config.config["server"]["terminal_map"]:
            os.system("cls" if os.name == "nt" else "clear")
            print(globals.my_game.scoreboard())
            print(globals.my_game.board.image())

        logger.info("Starting tick execution.")
        globals.my_game.execute_game_step(commands)

        logger.info("Waiting for game commands.")
        globals.time_of_next_execution = datetime.datetime.now() + datetime.timedelta(
            0, config.config["server"]["tick_wait_time"]
        )
        logger.info(f"Time of next execution: {globals.time_of_next_execution}")

        await asyncio.sleep(config.config["server"]["tick_wait_time"])
    globals.my_game.end_game()
    if config.config["server"]["terminal_map"]:
        os.system("cls" if os.name == "nt" else "clear")
        print(globals.my_game.scoreboard())
        print(globals.my_game.board.image())


async def get_all_queue_items(
    queue: asyncio.Queue[game.Order | object],
) -> list[game.Order]:
    items: list[game.Order] = []
    item = await queue.get()
    while item is not SENTINEL:
        items.append(item)  # pyright: ignore [reportArgumentType]
        queue.task_done()
        item = await queue.get()
    queue.task_done()
    return items
