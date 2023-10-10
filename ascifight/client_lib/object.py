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


class ExtendedActorDescription(ActorDescription):
    properties: data.ActorProperty


class Objects:
    """
    Basic objects.
    """

    def __init__(self, game_state: StateResponse, rules: RulesResponse, own_team: str):
        self.game_state = game_state
        self.rules = rules
        self.own_team = own_team
        self.extended_actors: list[ExtendedActorDescription] = [
            self._add_properties(actor, self.rules.actor_properties)
            for actor in self.game_state.actors
        ]
        self.conditions = Conditions(self)

    def own_actor(self, actor_id: int) -> ExtendedActorDescription:
        return next(
            actor
            for actor in self.extended_actors
            if actor.team == self.own_team and actor.ident == actor_id
        )

    def enemy_actor_by_id(self, actor_id: int, team: str) -> ExtendedActorDescription:
        return next(
            actor
            for actor in self.extended_actors
            if actor.team == team and actor.ident == actor_id
        )

    def actor_by_coordinates(
        self, coordinates: data.Coordinates
    ) -> ExtendedActorDescription:
        return next(
            actor for actor in self.extended_actors if actor.coordinates == coordinates
        )

    def enemy_actors_by_type(
        self, _type: str, team: str | None = None
    ) -> list[ExtendedActorDescription]:
        return [
            actor
            for actor in self.extended_actors
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

    def _add_properties(
        self, actor: ActorDescription, properties: list[data.ActorProperty]
    ) -> ExtendedActorDescription:
        _type = actor.type
        actor_properties = next(
            actor_property
            for actor_property in properties
            if actor.type == actor_property.type
        )
        return ExtendedActorDescription(
            type=actor.type,
            team=actor.team,
            ident=actor.ident,
            flag=actor.flag,
            coordinates=actor.coordinates,
            properties=actor_properties,
        )

    @property
    def coordinates_objects(self) -> defaultdict[data.Coordinates, Any]:
        coordinates: defaultdict[data.Coordinates, Any] = defaultdict(list)
        for actor in self.extended_actors:
            coordinates[actor.coordinates].append(actor)
        for flag in self.game_state.flags:
            coordinates[flag.coordinates].append(flag)
        for base in self.game_state.bases:
            coordinates[base.coordinates].append(base)
        for wall in self.walls:
            coordinates[wall.coordinates].append(wall)
        return coordinates

    @property
    def home_base(self) -> BaseDescription:
        return next(
            base for base in self.game_state.bases if base.team == self.own_team
        )

    @property
    def own_flag(self) -> FlagDescription:
        return next(
            flag for flag in self.game_state.flags if flag.team == self.own_team
        )

    @property
    def own_actors(self) -> list[ExtendedActorDescription]:
        return [actor for actor in self.extended_actors if actor.team == self.own_team]

    @property
    def enemy_actors(self) -> list[ExtendedActorDescription]:
        return [actor for actor in self.extended_actors if actor.team != self.own_team]

    @property
    def enemy_flags(self) -> list[FlagDescription]:
        return [flag for flag in self.game_state.flags if flag.team != self.own_team]

    @property
    def walls(self) -> list[WallDescription]:
        return [wall for wall in self.game_state.walls]

    @property
    def enemy_bases(self) -> list[BaseDescription]:
        return [base for base in self.game_state.bases if base.team != self.own_team]


class Conditions:
    def __init__(self, objects: Objects):
        self.objects = objects

    def we_have_the_flag(self, flag: FlagDescription):
        return any([actor.flag == flag for actor in self.objects.own_actors])

    @property
    def our_flag_is_at_home(self) -> bool:
        return self.objects.own_flag.coordinates == self.objects.home_base.coordinates

    def flag_is_at_home(self, flag: FlagDescription) -> bool:
        return flag.coordinates == self.objects.enemy_base(flag.team)
