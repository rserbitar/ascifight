import math
import dataclasses
import httpx
# hack if you want to use requests instead of httpx:
# import requests
# httpx = requests
import random
import structlog
import structlog.contextvars
import time

logger = structlog.get_logger()

server = 'http://127.0.0.1:8000/'
TEAM = ""
PASSWORD = ""

@dataclasses.dataclass
class Order:
    order_type: str
    actor: int
    direction: str
    team: str = TEAM
    password: str = PASSWORD


def place_order(order: Order):
    order_dict = dataclasses.asdict(order)
    order_type = order_dict.pop('order_type')
    url = server + f'{order_type}_order'
    httpx.post(url=url, json=order_dict)


def get_information(info_type: str):
    url = server + info_type
    response = httpx.get(url)
    return response.json()


def get_new_orders():
    pass

if __name__ == '__main__':
    current_tick = -1
    game_started = False

    while True:
        if not game_started:
            time_to_start = get_information('game_start')
            if time_to_start > 0:
                logger.info('waiting until game start', seconds=time_to_start)
                time.sleep(time_to_start)
            else:
                logger.info('game has started')
                game_started = True
        else:

            timing = get_information('timing')
            if timing['tick'] > current_tick:
                structlog.contextvars.bind_contextvars(tick=timing['tick'])
                orders = get_new_orders()
                for order in orders:
                    place_order(order)
                current_tick = timing['tick']
                logger.info('Placed orders')
            elif timing['tick'] < current_tick:
                time_to_start = get_information('game_start')
                if time_to_start > 0:
                    game_started = False
                # the game may have restarted, reset tick
                current_tick = -1
            else:
                sleep_duration_time = timing['time_to_next_execution']
                logger.info("sleeping", seconds=sleep_duration_time)
                if sleep_duration_time > 0:
                    time.sleep(sleep_duration_time)
                else:
                    logger.warning('Game appears to have ended', time_to_next_execution=sleep_duration_time)
                    game_started = False