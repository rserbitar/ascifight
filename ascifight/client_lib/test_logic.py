import structlog
from structlog.contextvars import (
    bind_contextvars,
)
import ascifight.client_lib.infra as asci_infra
import ascifight.client_lib.agents as asci_agents
import ascifight.client_lib.object as asci_object


logger = structlog.get_logger()


def execute():
    # necessary infrastructure here, do not change
    asci_infra.config["team"] = "Team 1"
    asci_infra.config["password"] = "1"
    state = asci_infra.get_game_state()
    rules = asci_infra.get_game_rules()
    team = asci_infra.config["team"]
    objects = asci_object.Objects(state, rules, team)

    bind_contextvars(tick=objects.game_state.tick)

    # put your execution code here

    flag_runner = asci_agents.NearestFlagRunner(objects, 0)
    flag_runner.execute()
    flag_sneaker = asci_agents.AvoidCenterFlagRunner(objects, 1)
    flag_sneaker.execute()
    attacker = asci_agents.NearestEnemyKiller(objects, 2)
    attacker.execute()
    guardian = asci_agents.Guardian(objects, 3)
    guardian.execute()

    # code for testing here!

    asci_infra.config["team"] = "Team 2"
    asci_infra.config["password"] = "2"
    state = asci_infra.get_game_state()
    rules = asci_infra.get_game_rules()
    team = asci_infra.config["team"]
    objects = asci_object.Objects(state, rules, team)

    bind_contextvars(tick=objects.game_state.tick)

    # put your execution code here

    flag_runner = asci_agents.NearestFlagRunner(objects, 0)
    flag_runner.execute()
    flag_sneaker = asci_agents.AvoidCenterFlagRunner(objects, 1)
    flag_sneaker.execute()
    attacker = asci_agents.NearestEnemyKiller(objects, 2)
    attacker.execute()
    guardian = asci_agents.Guardian(objects, 3)
    guardian.execute()
