from collections import defaultdict
from typing import Any

import ascifight.board.data as data
from ascifight.routers.states import (
    BaseDescription,
    RulesResponse,
    StateResponse,
    ActorDescription,
    FlagDescription,
    WallDescription,
)


class Objects:
    """
    Basic objects.
    """

    def __init__(self, game_state: StateResponse, rules: RulesResponse, own_team: str):
        self.game_state = game_state
        self.rules = rules
        self.own_team = own_team
        self.home_base = self._home_base()
        self.own_flag = self._own_flag()
        self.own_actors = self._own_actors()
        self.enemy_actors = self._enemy_actors()
        self.enemy_flags = self._enemy_flags()
        self.walls = self._walls()
        self.coordinates_objects = self._fill_coordinates()

    def own_actor(self, actor_id: int) -> ActorDescription:
        return next(
            actor
            for actor in self.game_state.actors
            if actor.team == self.own_team and actor.ident == actor_id
        )

    def enemy_actor_by_id(self, actor_id: int, team: str) -> ActorDescription:
        return next(
            actor
            for actor in self.game_state.actors
            if actor.team == team and actor.ident == actor_id
        )

    def actor_by_coordinates(self, coordinates: data.Coordinates) -> ActorDescription:
        return next(
            actor
            for actor in self.game_state.actors
            if actor.coordinates == coordinates
        )

    def enemy_actors_by_type(
        self, _type: str, team: str | None = None
    ) -> list[ActorDescription]:
        return [
            actor
            for actor in self.game_state.actors
            if (actor.team == team or team is None) and actor.type == _type
        ]

    def flag_by_coordinates(self, coordinates: data.Coordinates) -> FlagDescription:
        return next(
            flag for flag in self.game_state.flags if flag.coordinates == coordinates
        )

    def enemy_flag_by_team(self, team: str) -> FlagDescription:
        return next(flag for flag in self.game_state.flags if flag.team == team)

    def enemy_base(self, team: str) -> BaseDescription:
        return next(base for base in self.game_state.bases if base.team == team)

    def _fill_coordinates(self) -> defaultdict[data.Coordinates, Any]:
        coordinates: defaultdict[data.Coordinates, Any] = defaultdict(list)
        for actor in self.game_state.actors:
            coordinates[actor.coordinates].append(actor)
        for flag in self.game_state.flags:
            coordinates[flag.coordinates].append(flag)
        for base in self.game_state.bases:
            coordinates[base.coordinates].append(base)
        for wall in self.walls:
            coordinates[wall.coordinates].append(wall)
        return coordinates

    def _home_base(self) -> BaseDescription:
        return next(
            base for base in self.game_state.bases if base.team == self.own_team
        )

    def _own_flag(self) -> FlagDescription:
        return next(
            flag for flag in self.game_state.flags if flag.team == self.own_team
        )

    def _own_actors(self) -> list[ActorDescription]:
        return [
            actor for actor in self.game_state.actors if actor.team == self.own_team
        ]

    def _enemy_actors(self) -> list[ActorDescription]:
        return [
            actor for actor in self.game_state.actors if actor.team != self.own_team
        ]

    def _enemy_flags(self) -> list[FlagDescription]:
        return [flag for flag in self.game_state.flags if flag.team != self.own_team]

    def _walls(self) -> list[WallDescription]:
        return [wall for wall in self.game_state.walls]
