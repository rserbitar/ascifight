import httpx
import time

import structlog

import ascifight.client_lib.state as asci_state
import ascifight.client_lib.logic as logic
import ascifight.client_lib.infra as asci_infra

logger = structlog.get_logger()

state: asci_state.State | None = None
state2: asci_state.State | None = None


def game_loop():
    global state
    global state2
    current_tick = -1
    while True:
        try:
            timing = asci_infra.get_timing()
            # if the game tarted a new tick we need to issue orders
            if timing.tick != current_tick:
                if timing.tick < current_tick:
                    # the game may have restarted, reset tick
                    current_tick = timing.tick
                asci_infra.config["team"] = "Team 1"
                asci_infra.config["password"] = "1"
                state = logic.execute(state)
                asci_infra.config["team"] = "Team 2"
                asci_infra.config["password"] = "2"
                state2 = logic.execute(state2)
                current_tick = timing.tick
                logger.info(f"Issued orders for tick {current_tick}.")
            # sleep the time the server says it will take till next tick
            sleep_duration_time = timing.time_to_next_execution
            logger.info(f"sleeping for {sleep_duration_time} seconds.")
            if sleep_duration_time >= 0:
                time.sleep(sleep_duration_time)
        except httpx.ConnectError:
            logger.info("Server not started. Sleeping 5 seconds.")
            current_tick = -1
            time.sleep(5)
            continue


if __name__ == "__main__":
    game_loop()
