import httpx


import enum
import structlog
import structlog.contextvars
import time

logger = structlog.get_logger()

SERVER = "http://127.0.0.1:8000/"
TEAM = "Team 1"
PASSWORD = "1"


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
    teams = state["teams"].copy()
    teams.remove(TEAM)
    target_team = teams[0]
    target_base = [base for base in state["bases"] if base["team"] == target_team][0]
    target_coordinates = target_base["coordinates"]
    home_base = [base for base in state["bases"] if base["team"] == TEAM][0]
    home_coordinates = home_base["coordinates"]
    actor = [actor for actor in state["actors"] if actor["team"] == TEAM][0]
    actor_coordinates = actor["coordinates"]
    if not actor["flag"]:
        direction = httpx.post(
            url=f"{SERVER}computations/direction",
            json={"origin": actor_coordinates, "target": target_coordinates},
        ).json()
        print(direction)
        if (
            httpx.post(
                url=f"{SERVER}computations/distance",
                json={"origin": actor_coordinates, "target": target_coordinates},
            ).json()
            == 1
        ):
            httpx.post(
                url=f"{SERVER}orders/grabput/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )
        else:
            httpx.post(
                url=f"{SERVER}orders/move/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )
    else:
        direction = httpx.post(
            url=f"{SERVER}computations/direction",
            json={"origin": actor_coordinates, "target": home_coordinates},
        ).json()[0]
        if (
            httpx.post(
                url=f"{SERVER}computations/distance",
                json={"origin": actor_coordinates, "target": home_coordinates},
            ).json()
            == 1
        ):
            httpx.post(
                url=f"{SERVER}orders/grabput/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )
        else:
            httpx.post(
                url=f"{SERVER}orders/move/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )


def place_order(order: Orders, actor: int, direction: Directions) -> httpx.Response:
    url: str = SERVER + "orders/" + order + f"{actor}"
    return httpx.post(url=url, params={"direction": direction}, auth=(TEAM, PASSWORD))


def get_information(info_type: str):
    url = SERVER + "states/" + info_type
    response = httpx.get(url)
    return response.json()


def game_loop():
    current_tick = -1
    game_started = False
    while True:
        try:
            if not game_started:
                time_to_start = get_information("game_start")
                if time_to_start > 0:
                    logger.info("waiting until game starts.", seconds=time_to_start)
                    time.sleep(time_to_start)
                else:
                    logger.info("Game has started.")
                    game_started = True
            else:
                timing = get_information("timing")
                print(timing)
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
                    if sleep_duration_time >= 0:
                        time.sleep(sleep_duration_time)
                    else:
                        logger.warning(
                            "Game appears to have ended.",
                            time_to_next_execution=sleep_duration_time,
                        )
                        game_started = False
        except httpx.ConnectError:
            logger.info("Server not started. Sleeping 10 seconds.")
            current_tick = -1
            game_started = False
            time.sleep(10)
            continue


if __name__ == "__main__":
    game_loop()
