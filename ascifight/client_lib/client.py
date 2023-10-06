import httpx
import logging
import time

import ascifight.client_lib.infra as infra
import ascifight.client_lib.metrics as metrics
import ascifight.client_lib.basic as basic
import ascifight.client_lib.object as object


logger = logging.getLogger()
logging.basicConfig(level="INFO")


def execute():
    # necessary infrastructure here, do not change
    state = infra.get_game_state()
    rules = infra.get_game_rules()
    team = infra.config["team"]
    objects = object.Objects(state, rules, team)

    # put your execution code here

    # which metric to use for way finding
    metric_used = metrics.BasicMetric(objects)
    # the actor to use
    actor = objects.own_actor(0)

    # identifying the target
    target_flag = basic.nearest_enemy_flag(actor, actor.team, state, metric_used)

    home_base = objects.home_base

    # if we already have the flag
    if actor.flag == target_flag.team:
        distance = metric_used.distance(actor.coordinates, home_base.coordinates)
        direction = metric_used.next_direction(actor.coordinates, home_base.coordinates)
        # we are further away
        logger.info(f"Distance: {distance}")
        if distance > 1:
            logger.info("Heading home!")
            infra.issue_order(order="move", actor_id=actor.ident, direction=direction)
        # we stand right before home base
        else:
            logger.info("Putting flag!")
            infra.issue_order(
                order="grabput", actor_id=actor.ident, direction=direction
            )
    # we dont have the flag
    else:
        distance = metric_used.distance(actor.coordinates, target_flag.coordinates)
        direction = metric_used.next_direction(
            actor.coordinates, target_flag.coordinates
        )
        # we are further away
        logger.info(f"Distance: {distance}")
        if distance > 1:
            logger.info("Heading for flag!")
            infra.issue_order(order="move", actor_id=actor.ident, direction=direction)
        # we stand right before enemy flag
        else:
            logger.info("Grabbing flag!")
            infra.issue_order(
                order="grabput", actor_id=actor.ident, direction=direction
            )


def game_loop():
    current_tick = -1
    while True:
        try:
            timing = infra.get_timing()
            # if the game tarted a new tick we need to issue orders
            if timing.tick != current_tick:
                if timing.tick < current_tick:
                    # the game may have restarted, reset tick
                    current_tick = timing.tick
                execute()
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
