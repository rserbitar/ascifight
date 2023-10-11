import structlog
from structlog.contextvars import (
    bind_contextvars,
)

import ascifight.client_lib.infra as asci_infra
import ascifight.client_lib.agents as asci_agents
import ascifight.client_lib.state as asci_state


logger = structlog.get_logger()


def execute(state: asci_state.State | None) -> asci_state.State:
    # necessary infrastructure here, do not change
    if not state:
        rules = asci_infra.get_game_rules()
        all_actions = asci_infra.get_all_actions()
        state = asci_state.State(
            own_team=asci_infra.config["team"], rules=rules, actions=all_actions
        )
    game_state = asci_infra.get_game_state()
    current_actions = asci_infra.get_current_actions()
    state.new_tick(game_state=game_state, current_actions=current_actions)

    bind_contextvars(tick=state.tick)

    # put your execution code here

    flag_runner = asci_agents.NearestFlagRunner(state, 0)
    flag_runner.execute()
    flag_sneaker = asci_agents.AvoidCenterFlagRunner(state, 1)
    flag_sneaker.execute()
    attacker = asci_agents.NearestEnemyKiller(state, 2)
    attacker.execute()
    guardian = asci_agents.Defender(state, 3)
    guardian.execute()

    return state
