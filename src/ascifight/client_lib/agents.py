from abc import ABC, abstractmethod
import structlog
from structlog.contextvars import (
    bound_contextvars,
)

import ascifight.board.data as asci_data
import ascifight.client_lib.infra as asci_infra
import ascifight.client_lib.metrics as asci_metrics
import ascifight.client_lib.basic_functions as asci_basic
import ascifight.client_lib.state as asci_state

from ascifight.routers.states import (
    FlagDescription,
)


class Agent(ABC):
    def __init__(self, state: asci_state.State, ident: int) -> None:
        self.state = state
        self.objects = state.objects
        self.rules = state.rules
        self.conditions = state.conditions
        self.me = self.objects.own_actor(ident)
        self.properties = next(
            prop for prop in self.rules.actor_properties if prop.type == self.me.type
        )
        self._logger = structlog.get_logger()

    def execute(self) -> None:
        with bound_contextvars(actor=self.me.ident):
            self._execute()

    @abstractmethod
    def _execute(self) -> None:
        pass

    def bring_flag_home(self, metric: asci_metrics.Metric):
        """
        Try to get back to the home base, using the given metric and place the flag
        on the home base.
        """
        home_base = self.objects.home_base
        home_base_distance = metric.path_distance(
            self.me.coordinates, home_base.coordinates
        )
        home_base_direction = metric.next_direction(
            self.me.coordinates, home_base.coordinates
        )

        self._logger.info(f"Distance: to home_base {home_base_distance}")
        if home_base_direction is None:
            self._logger.info("No path!")
        elif home_base_distance > 1:
            self._logger.info("Heading home!")
            asci_infra.issue_order(
                order="move", actor_id=self.me.ident, direction=home_base_direction
            )
        else:
            self._logger.info("Putting flag!")
            asci_infra.issue_order(
                order="grabput",
                actor_id=self.me.ident,
                direction=home_base_direction,
            )

    def get_flag(self, target_flag: FlagDescription, metric: asci_metrics.Metric):
        """
        Try to ge to the targeted flags using the supplied metric
        and grab it once within reach.
        """
        self.move_to_destination(destination=target_flag.coordinates, metric=metric)

        flag_distance = metric.path_distance(
            self.me.coordinates, target_flag.coordinates
        )
        flag_direction = metric.next_direction(
            self.me.coordinates, target_flag.coordinates
        )

        # if distance is 2 it will be 1 after moving and thus can already be grabbed
        if flag_distance <= 2 and flag_direction is not None:
            self._logger.info("Grabbing flag!")
            asci_infra.issue_order(
                order="grabput", actor_id=self.me.ident, direction=flag_direction
            )

    def attack(
        self,
        target: asci_state.ExtendedActorDescription,
        move_metric: asci_metrics.Metric,
        target_metric: asci_metrics.Metric | None = None,
    ):
        """Try to move to the target using the supplied moving metric and
        then attack is using the supplied target metric."""
        if not target_metric:
            target_metric = move_metric

        self.move_to_destination(destination=target.coordinates, metric=move_metric)

        enemy_target_distance = target_metric.path_distance(
            self.me.coordinates, target.coordinates
        )
        enemy_target_direction = target_metric.next_direction(
            self.me.coordinates, target.coordinates
        )
        # as both attacker and target could have moved is makes sense to attack
        # even when distance is 3 before moving
        if enemy_target_direction is None:
            self._logger.info("No direction to hit.")
        else:
            if enemy_target_distance <= 3:
                self._logger.info("Attacking!")
                asci_infra.issue_order(
                    order="attack",
                    actor_id=self.me.ident,
                    direction=enemy_target_direction,
                )

    def target_and_get_flag(self, metric: asci_metrics.Metric):
        # we dont have a flag
        if self.me.flag is None:
            target_flag = asci_basic.nearest_enemy_flag(self.me, self.objects, metric)

            if self.conditions.we_have_the_flag(target_flag):
                target_destination = self.objects.enemy_base(
                    target_flag.team
                ).coordinates
                self.move_to_destination(target_destination, metric)
            else:
                self.get_flag(target_flag, metric)
        # if we already have a flag
        else:
            self.bring_flag_home(metric)

    def move_to_destination(
        self, destination: asci_data.Coordinates, metric: asci_metrics.Metric
    ):
        """
        Move to destination coordinates using the supplied metric.
        """
        destination_distance = metric.path_distance(self.me.coordinates, destination)
        destination_direction = metric.next_direction(self.me.coordinates, destination)
        self._logger.info(f"Distance to destination: {destination_distance}")
        if destination_direction is None:
            self._logger.info("No path!")
        else:
            if destination_distance > 1:
                self._logger.info("Heading for destination!")
                asci_infra.issue_order(
                    order="move",
                    actor_id=self.me.ident,
                    direction=destination_direction,
                )


class NearestFlagRunner(Agent):
    """
    This agent:
    * runs to the nearest flag
        * avoids enemy attackers while doing so
    * grabs the target flag
    * runs back to home base
        * ignores enemy attackers while doing so
    * puts the flag ont he home base
    """

    def _execute(self) -> None:
        avoid_attackers_weights = asci_metrics.WeightsGenerator(
            self.state
        ).avoid_attackers()
        avoid_killer_metric = asci_metrics.DijkstraMetric(
            self.state, weights=avoid_attackers_weights
        )

        self.target_and_get_flag(avoid_killer_metric)


class AvoidCenterFlagRunner(Agent):
    """
    This agent:
    * runs to the nearest flag
        * avoids enemy attackers while doing so
    * grabs the target flag
    * runs back to home base
        * ignores enemy attackers while doing so
    * puts the flag ont he home base
    """

    def _execute(self) -> None:
        avoid_attackers_weights = asci_metrics.WeightsGenerator(
            self.state
        ).avoid_attackers()
        center = self.rules.map_size / 2 - 0.5
        avoid_function = asci_metrics.gaussian_factory(5, self.rules.map_size / 3)
        avoid_center_weights = asci_metrics.WeightsGenerator(
            self.state
        ).avoid_coordinates(center, center, avoid_function)

        avoid_center_and_killer_metric = asci_metrics.DijkstraMetric(
            self.state, weights=avoid_attackers_weights + avoid_center_weights
        )

        self.target_and_get_flag(avoid_center_and_killer_metric)


class NearestEnemyKiller(Agent):
    """
    This agent:
    * runs to the nearest enemy
    * tries to attack it
    * runs to the next nearest enemy
    """

    def _execute(self) -> None:
        blockers = asci_metrics.BlockersGenerator(self.state).standard_blockers(
            blocking_enemy_actors=False
        )
        metric = asci_metrics.DijkstraMetric(self.state, blockers=blockers)
        target = asci_basic.nearest_enemy(self.me, self.objects, metric)
        self.attack(target, metric)


class Defender(Agent):
    """
    This agent:
    * runs to the nearest enemy
        * stays in an area around the flag while doing so
    * tries to attack it
    * runs to the next nearest enemy
    """

    def _execute(self) -> None:
        blockers = asci_metrics.BlockersGenerator(self.state).standard_blockers(
            blocking_enemy_actors=False
        )
        # create weights for a virtual fence around the base
        defend_base_weights = asci_metrics.WeightsGenerator(self.state).guard_base()

        # this metric will use weights to stop moving beyond a given distance
        move_metric = asci_metrics.DijkstraMetric(
            self.state, blockers=blockers, weights=defend_base_weights
        )
        # ths metric will be used for targeting to target and hit enemies
        # beyond/at the virtual move wall

        target_metric = asci_metrics.DijkstraMetric(self.state, blockers=blockers)
        target = asci_basic.nearest_enemy(self.me, self.objects, target_metric)
        self.attack(target=target, move_metric=move_metric, target_metric=target_metric)
