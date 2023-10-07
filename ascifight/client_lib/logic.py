import structlog

import ascifight.client_lib.infra as asci_infra
import ascifight.client_lib.agents as asci_agents
import ascifight.client_lib.object as asci_object


logger = structlog.get_logger()


def execute():
    # necessary infrastructure here, do not change
    state = asci_infra.get_game_state()
    rules = asci_infra.get_game_rules()
    team = asci_infra.config["team"]
    objects = asci_object.Objects(state, rules, team)

    # put your execution code here

    flag_runner = asci_agents.NearestFlagRunner(objects, 0)
    flag_runner.execute()
