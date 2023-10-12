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
    state = asci_infra.update_state(state)
    bind_contextvars(tick=state.tick)

    # put your execution code here

    flag_runner = asci_agents.NearestFlagRunner(state, ident=0)
    flag_runner.execute()
    flag_sneaker = asci_agents.AvoidCenterFlagRunner(state, ident=1)
    flag_sneaker.execute()
    attacker = asci_agents.NearestEnemyKiller(state, ident=2)
    attacker.execute()
    guardian = asci_agents.Defender(state, ident=3)
    guardian.execute()

    return state
