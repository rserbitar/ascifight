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
    # this teams flag we want to get
    target_team = teams[0]
    # this is the base we need to go to, suppose their flag is there?
    target_base = [base for base in state["bases"] if base["team"] == target_team][0]
    # these are the bases coordinates
    target_coordinates = target_base["coordinates"]
    # this is our base
    home_base = [base for base in state["bases"] if base["team"] == TEAM][0]
    # we need the coordinates when we want to go home
    home_coordinates = home_base["coordinates"]
    # we will just use the first of our actors we have
    # suppose that it will be able to grab the flag
    actor = [actor for actor in state["actors"] if actor["team"] == TEAM][0]
    # thats where the actor currently is
    actor_coordinates = actor["coordinates"]
    # if it doesn't have the flag it needs to go to the enemy base
    if not actor["flag"]:
        # we can calculate the direction of the enemy base or get it from the server
        direction = httpx.post(
            url=f"{SERVER}computations/direction",
            json={"origin": actor_coordinates, "target": target_coordinates},
        ).json()
        # we need to stop if we are standing right next to the base
        if (
            httpx.post(
                url=f"{SERVER}computations/distance",
                json={"origin": actor_coordinates, "target": target_coordinates},
            ).json()
            == 1
        ):
            # and grab the flag, the direction is the one we would have walked to
            httpx.post(
                url=f"{SERVER}orders/grabput/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )
        # if we are not there yet we need to go
        else:
            httpx.post(
                url=f"{SERVER}orders/move/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )
    # if it has the flag we need to head home
    else:
        # where is home?
        direction = httpx.post(
            url=f"{SERVER}computations/direction",
            json={"origin": actor_coordinates, "target": home_coordinates},
        ).json()[0]
        # if we are already just 1 space apart we are there
        if (
            httpx.post(
                url=f"{SERVER}computations/distance",
                json={"origin": actor_coordinates, "target": home_coordinates},
            ).json()
            == 1
        ):
            # we put the flag on our base
            httpx.post(
                url=f"{SERVER}orders/grabput/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )
        else:
            # if we are not there we slog on home
            httpx.post(
                url=f"{SERVER}orders/move/{actor['ident']}",
                params={"direction": direction},
                auth=(TEAM, PASSWORD),
            )


def get_information(info_type: str):
    url = SERVER + "states/" + info_type
    response = httpx.get(url)
    return response.json()


def game_loop():
    current_tick = -1
    while True:
        try:
            timing = get_information("timing")
            # if the game tarted a new tick we need to issue orders
            if timing["tick"] != current_tick:
                if timing["tick"] < current_tick:
                    # the game may have restarted, reset tick
                    current_tick = timing["tick"]
                structlog.contextvars.bind_contextvars(tick=timing["tick"])
                execute()
                current_tick = timing["tick"]
                logger.info("Issued orders for tick.")
            # sleep the time the server says it will take till next tick
            sleep_duration_time = timing["time_to_next_execution"]
            logger.info("sleeping", seconds=sleep_duration_time)
            if sleep_duration_time >= 0:
                time.sleep(sleep_duration_time)
        except httpx.ConnectError:
            structlog.contextvars.unbind_contextvars("tick")
            logger.info("Server not started. Sleeping 5 seconds.")
            current_tick = -1
            time.sleep(5)
            continue


if __name__ == "__main__":
    game_loop()
