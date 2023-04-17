import datetime
import asyncio


import ascifight.game as game

# TODO: fix times if game has not yet started
time_to_next_execution: datetime.timedelta
time_of_next_execution: datetime.datetime
my_game: game.Game
command_queue: asyncio.Queue[game.Order | object] = asyncio.Queue()
