from abc import ABC, abstractmethod
import structlog
from structlog.contextvars import (
    bound_contextvars,
)

import ascifight.board.data as asci_data
import ascifight.client_lib.infra as asci_infra
import ascifight.client_lib.metrics as asci_metrics
import ascifight.client_lib.basic_functions as asci_basic
import ascifight.client_lib.object as asci_object

from ascifight.routers.states import (
    FlagDescription,
    WallDescription,
)


class Agent(ABC):
    def __init__(self, objects: asci_object.Objects, id: int) -> None:
        self.objects = objects
        self.me = objects.own_actor(id)
        self.properties = next(
            prop
            for prop in self.objects.rules.actor_properties
            if prop.type == self.me.type
        )
        self._logger = structlog.get_logger()

    def execute(self) -> None:
        with bound_contextvars(actor=self.me.ident):
            self._execute()

    @abstractmethod
    def _execute(self) -> None:
        pass

    def bring_flag_home(self, metric: asci_metrics.DijkstraMetric):
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

    def get_flag(
        self, target_flag: FlagDescription, metric: asci_metrics.DijkstraMetric
    ):
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
        target: asci_object.ExtendedActorDescription,
        move_metric: asci_metrics.DijkstraMetric,
        target_metric: asci_metrics.DijkstraMetric | None = None,
    ):
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

    def move_to_destination(
        self, destination: asci_data.Coordinates, metric: asci_metrics.DijkstraMetric
    ):
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
    This agent :
    * runs to the nearest flag
        * avoids enemy attackers while doing so
    * grabs the target flag
    * runs back to home base
        * ignores enemy attackers while doing so
    * puts the flag ont he home base
    """

    def _execute(self) -> None:
        avoid_attackers_weights = asci_metrics.WeightsGenerator(
            self.objects
        ).avoid_attackers()
        avoid_killer_metric = asci_metrics.DijkstraMetric(
            self.objects, weights=avoid_attackers_weights
        )
        target_flag = asci_basic.nearest_enemy_flag(
            self.me, self.objects, avoid_killer_metric
        )

        # if we already have the flag
        if self.me.flag == target_flag.team:
            metric = asci_metrics.DijkstraMetric(self.objects)
            self.bring_flag_home(metric)
        # we dont have the flag
        else:
            self.get_flag(target_flag, avoid_killer_metric)


class AvoidCenterFlagRunner(Agent):
    """
    This agent :
    * runs to the nearest flag
        * avoids enemy attackers while doing so
    * grabs the target flag
    * runs back to home base
        * ignores enemy attackers while doing so
    * puts the flag ont he home base
    """

    def _execute(self) -> None:
        avoid_attackers_weights = asci_metrics.WeightsGenerator(
            self.objects
        ).avoid_attackers()
        center = self.objects.rules.map_size / 2 - 0.5
        avoid_function = asci_metrics.gaussian_factory(
            5, self.objects.rules.map_size / 3
        )
        avoid_center_weights = asci_metrics.WeightsGenerator(
            self.objects
        ).avoid_coordinates(center, center, avoid_function)

        avoid_center_and_killer_metric = asci_metrics.DijkstraMetric(
            self.objects, weights=avoid_attackers_weights + avoid_center_weights
        )

        target_flag = asci_basic.nearest_enemy_flag(
            self.me, self.objects, avoid_center_and_killer_metric
        )

        # if we already have the flag
        if self.me.flag == target_flag.team:
            self.bring_flag_home(avoid_center_and_killer_metric)
        # we dont have the flag
        else:
            self.get_flag(target_flag, avoid_center_and_killer_metric)


class NearestEnemyKiller(Agent):
    """
    This agent :
    * runs to the nearest enemy
    * tries to attack it
    * runs to the next nearest enemy
    """

    def _execute(self) -> None:
        blockers = asci_metrics.BlockersGenerator(self.objects).standard_blockers(
            blocking_enemy_actors=False
        )
        metric = asci_metrics.DijkstraMetric(self.objects, blockers=blockers)
        target = asci_basic.nearest_enemy(self.me, self.objects, metric)
        self.attack(target, metric)


class Guardian(Agent):
    """
    This agent :
    * runs to the nearest enemy
        * stays in an area around the flag while doing so
    * tries to attack it
    * runs to the next nearest enemy
    """

    def _execute(self) -> None:
        blockers = asci_metrics.BlockersGenerator(self.objects).standard_blockers(
            blocking_enemy_actors=False
        )
        # create weights for a virtual fence around the base
        guard_base_weights = asci_metrics.WeightsGenerator(self.objects).guard_base()

        # this metric will use weights to stop moving beyond a given distance
        move_metric = asci_metrics.DijkstraMetric(
            self.objects, blockers=blockers, weights=guard_base_weights
        )
        # ths metric will be sued for targeting to target and hit enemies
        # beyond/at the virtual move wall

        target_metric = asci_metrics.DijkstraMetric(self.objects, blockers=blockers)
        target = asci_basic.nearest_enemy(self.me, self.objects, target_metric)
        self.attack(target=target, move_metric=move_metric, target_metric=target_metric)
