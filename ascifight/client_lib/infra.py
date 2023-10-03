import os
import toml
import httpx

from ascifight.board.actions import Directions
import ascifight.routers.states

global config
absolute_path = os.path.dirname(__file__)
with open(file=f"{absolute_path}/config.toml", mode="r") as fp:
    config = toml.load(fp)


def get_game_state() -> ascifight.routers.states.StateResponse:
    url = config["server"] + "states/game_state"
    response = httpx.get(url)
    return ascifight.routers.states.StateResponse.model_validate(response.json())


def get_current_actions() -> ascifight.routers.states.CurrentActionsResponse:
    url = config["server"] + "states/current_actions"
    response = httpx.get(url)
    return ascifight.routers.states.CurrentActionsResponse.model_validate(
        response.json()
    )


def get_all_actions() -> ascifight.routers.states.AllActionsResponse:
    url = config["server"] + "states/all_actions"
    response = httpx.get(url)
    return ascifight.routers.states.AllActionsResponse.model_validate(response.json())


def get_game_rules() -> ascifight.routers.states.RulesResponse:
    url = config["server"] + "states/get_game_rules"
    response = httpx.get(url)
    return ascifight.routers.states.RulesResponse.model_validate(response.json())


def get_timing() -> ascifight.routers.states.TimingResponse:
    url = config["server"] + "states/timing"
    response = httpx.get(url)
    return ascifight.routers.states.TimingResponse.model_validate(response.json())


def issue_order(order: str, actor_id: int, direction: Directions):
    httpx.post(
        url=f"{config['server']}orders/{order}/{actor_id}",
        params={"direction": direction.value},
        auth=(config["team"], str(config["password"])),
    )
