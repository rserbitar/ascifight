from abc import ABC, abstractmethod
import structlog
from structlog.contextvars import (
    bind_contextvars,
    bound_contextvars,
)

import ascifight.client_lib.infra as asci_infra
import ascifight.client_lib.metrics as asci_metrics
import ascifight.client_lib.basic_functions as asci_basic
import ascifight.client_lib.object as asci_object

from ascifight.routers.states import (
    ActorDescription,
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


class NearestFlagRunner(Agent):
    def _execute(self) -> None:
        metric_used = asci_metrics.DijkstraMetric(
            asci_metrics.PathTopology(self.objects)
        )
        target_flag = asci_basic.nearest_enemy_flag(self.me, self.objects, metric_used)

        # if we already have the flag
        if self.me.flag == target_flag.team:
            self.bring_flag_home()
        # we dont have the flag
        else:
            self.get_flag(target_flag)

    def bring_flag_home(self):
        home_base = self.objects.home_base

        metric_used = asci_metrics.DijkstraMetric(
            asci_metrics.PathTopology(self.objects)
        )
        home_base_distance = metric_used.distance(
            self.me.coordinates, home_base.coordinates
        )
        home_base_direction = metric_used.next_direction(
            self.me.coordinates, home_base.coordinates
        )

        self._logger.info(f"Distance: to home_base {home_base_distance}")
        if home_base_direction is None:
            self._logger.info("No path!")
        elif home_base_distance > 2:
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

    def get_flag(self, target_flag: FlagDescription):
        metric_used = asci_metrics.DijkstraMetric(
            asci_metrics.PathTopology(self.objects)
        )

        flag_distance = metric_used.distance(
            self.me.coordinates, target_flag.coordinates
        )
        flag_direction = metric_used.next_direction(
            self.me.coordinates, target_flag.coordinates
        )

        self._logger.info(f"Distance to flag: {flag_distance}")
        if flag_direction is None:
            self._logger.info("No path!")
        elif flag_distance > 2:
            self._logger.info("Heading for flag!")
            asci_infra.issue_order(
                order="move", actor_id=self.me.ident, direction=flag_direction
            )
        else:
            self._logger.info("Grabbing flag!")
            asci_infra.issue_order(
                order="grabput", actor_id=self.me.ident, direction=flag_direction
            )


class NearestEnemyKiller(Agent):
    def _execute(self) -> None:
        metric_used = asci_metrics.DijkstraMetric(
            asci_metrics.PathTopology(self.objects)
        )
        target = asci_basic.nearest_enemy(self.me, self.objects, metric_used)

        self.kill(target)

    def kill(self, target: ActorDescription):
        metric_used = asci_metrics.DijkstraMetric(
            asci_metrics.PathTopology(self.objects)
        )

        enemy_distance = metric_used.distance(self.me.coordinates, target.coordinates)
        flag_direction = metric_used.next_direction(
            self.me.coordinates, target.coordinates
        )

        self._logger.info(f"Distance to enemy: {enemy_distance}")
        if flag_direction is None:
            self._logger.info("No path!")
        elif enemy_distance > 2:
            self._logger.info("Heading for target!")
            asci_infra.issue_order(
                order="move", actor_id=self.me.ident, direction=flag_direction
            )
        else:
            self._logger.info("Attacking!")
            asci_infra.issue_order(
                order="attack", actor_id=self.me.ident, direction=flag_direction
            )
