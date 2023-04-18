import httpx


import enum
import structlog
import structlog.contextvars
import time

logger = structlog.get_logger()

SERVER = "http://127.0.0.1:8000/"
TEAM = ""
PASSWORD = ""


class Orders(str, enum.Enum):
    move = "move"
    attack = "attack"
    grabput = "grabput"


class Directions(str, enum.Enum):
    left = "left"
    right = "right"
    down = "down"
    up = "up"


def execute():
    # put your execution code here
    state = get_information("game_state")
    # place_order(Orders.move, 0, Directions.left)


def place_order(order: Orders, actor: int, direction: Directions) -> httpx.Response:
    url: str = SERVER + "orders/" + order + f"{actor}"
    return httpx.post(url=url, params={"direction": direction}, auth=(TEAM, PASSWORD))


def get_information(info_type: str):
    url = SERVER + info_type
    response = httpx.get(url)
    return response.json()


def game_loop():
    current_tick = -1
    game_started = False
    while True:
        if not game_started:
            try:
                time_to_start = get_information("game_start")
                if time_to_start > 0:
                    logger.info("waiting until game starts.", seconds=time_to_start)
                    time.sleep(time_to_start)
                else:
                    logger.info("Game has started.")
                    game_started = True
            except httpx.ConnectError:
                logger.info("Server not started. Sleeping 10 seconds.")
                time.sleep(10)
                continue
        else:
            timing = get_information("timing")
            if timing["tick"] > current_tick:
                structlog.contextvars.bind_contextvars(tick=timing["tick"])
                execute()
                current_tick = timing["tick"]
                logger.info("Executed tick.")
            elif timing["tick"] < current_tick:
                time_to_start = get_information("game_start")
                if time_to_start > 0:
                    game_started = False
                # the game may have restarted, reset tick
                current_tick = -1
            else:
                sleep_duration_time = timing["time_to_next_execution"]
                logger.info("sleeping", seconds=sleep_duration_time)
                if sleep_duration_time > 0:
                    time.sleep(sleep_duration_time)
                else:
                    logger.warning(
                        "Game appears to have ended.",
                        time_to_next_execution=sleep_duration_time,
                    )
                    game_started = False


if __name__ == "__main__":
    game_loop()
