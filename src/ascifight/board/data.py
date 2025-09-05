from __future__ import annotations

import abc
import sys
import itertools
import typing
from functools import total_ordering

from pydantic import BaseModel, Field
import structlog

import ascifight.config as config
import ascifight.util as util


class Team(BaseModel):
    name: str
    password: str
    number: int

    @typing.override
    def __eq__(self, another: typing.Any):
        return hasattr(another, "name") and self.name == another.name

    @typing.override
    def __hash__(self):
        return hash(self.name)

    @typing.override
    def __str__(self):
        return f"Team {self.name}"


@total_ordering
class Coordinates(BaseModel):
    x: int = Field(
        description=(
            "X coordinate is decreased by the 'left' and increased by the"
            " 'right' direction."
        ),
        ge=0,
        le=config.config["game"]["map_size"] - 1,
    )
    y: int = Field(
        description=(
            "Y coordinate is decreased by the 'down' and increased by the"
            " 'up' direction."
        ),
        ge=0,
        le=config.config["game"]["map_size"] - 1,
    )

    @typing.override
    def __str__(self) -> str:
        return f"({self.x}/{self.y})"

    @typing.override
    def __eq__(self, another: typing.Any):
        return (
            hasattr(another, "x")
            and self.x == another.x
            and hasattr(another, "y")
            and self.y == another.y
        )

    @typing.override
    def __ne__(self, another: typing.Any):
        return (
            hasattr(another, "x")
            and hasattr(another, "y")
            and (self.x != another.x or self.y != another.y)
        )

    def __lt__(self, another: typing.Any):
        return (
            hasattr(another, "x")
            and hasattr(another, "y")
            and self.x * self.x + self.y * self.y
            > another.x * another.x + another.y * another.y
        )

    @typing.override
    def __hash__(self) -> int:
        return hash((self.x, self.y))


class ActorProperty(BaseModel):
    type: str
    grab: float = Field(
        description=(
            "The probability to successfully grab or put the flag. "
            "An actor with 0 can not carry the flag. Not even when it is given to it."
        ),
    )
    attack: float = Field(
        description=(
            "The probability to successfully attack. An actor with 0 can " "not attack."
        ),
    )
    build: float = Field(description="The probability to successfully build a wall.")
    destroy: float = Field(
        description="The probability to successfully destroy a wall."
    )


# Abstract class, using multiple inheritance with abc yields a pyright error
class BoardObject(  # pyright: ignore [reportUnsafeMultipleInheritance]
    BaseModel, abc.ABC
):
    pass


class Flag(BoardObject):
    team: Team
    board: BoardData

    @typing.override
    def __eq__(self, another: typing.Any):
        return (
            self.__class__.__name__ == another.__class__.__name__
            and hasattr(another, "team")
            and self.team.name == another.team.name
        )

    @typing.override
    def __hash__(self):
        return hash((self.__class__.__name__, self.team.name))

    @property
    def coordinates(self) -> Coordinates:
        return self.board.flags_coordinates[self]


class Actor(BoardObject, abc.ABC):
    ident: int
    team: Team
    board: BoardData
    grab: typing.ClassVar[float] = 0.0
    attack: typing.ClassVar[float] = 0.0
    build: typing.ClassVar[float] = 0.0
    destroy: typing.ClassVar[float] = 0.0
    flag: Flag | None = None

    @typing.override
    def __str__(self):
        return f"Actor ({self.__class__.__name__}) {self.team}-{self.ident}"

    @typing.override
    def __eq__(self, another: typing.Any):
        return (
            self.__class__.__name__ == another.__class__.__name__
            and hasattr(another, "ident")
            and self.ident == another.ident
            and hasattr(another, "team")
            and self.team == another.team
        )

    @typing.override
    def __hash__(self):
        return hash((self.__class__.__name__, self.ident, self.team))

    @classmethod
    def get_properties(cls) -> ActorProperty:
        return ActorProperty(
            type=cls.__name__,
            grab=cls.grab,
            attack=cls.attack,
            build=cls.build,
            destroy=cls.destroy,
        )

    @property
    def coordinates(self) -> Coordinates:
        return self.board.actors_coordinates[self]


class Generalist(Actor):
    grab: typing.ClassVar[float] = 1.0
    attack: typing.ClassVar[float] = 1.0


class Runner(Actor):
    grab: typing.ClassVar[float] = 1.0


class Attacker(Actor):
    attack: typing.ClassVar[float] = 1.0


class Guardian(Actor):
    pass


class Builder(Actor):
    build: typing.ClassVar[float] = 0.2


class Destroyer(Actor):
    destroy: typing.ClassVar[float] = 0.25


class Base(BoardObject):
    team: Team

    @typing.override
    def __eq__(self, another: typing.Any):
        return (
            self.__class__.__name__ == another.__class__.__name__
            and hasattr(another, "team")
            and self.team.name == another.team.name
        )

    @typing.override
    def __hash__(self):
        return hash((self.__class__.__name__, self.team.name))


class Wall(BoardObject):
    pass


@typing.final
class BoardData(BaseModel):  # pyright: ignore [reportUninitializedInstanceVariable]

    teams_data: list[dict[str, str]] = config.config["teams"]
    actors_data: list[str] = config.config["game"]["actors"]
    map_size: int = config.config["game"]["map_size"]
    walls: int = config.config["game"]["walls"]

    _logger: typing.Any

    names_teams: dict[str, Team] = {}
    teams: list[Team] = []
    actor_classes: list[type[Actor]] = []
    teams_actors: dict[tuple[Team, int], Actor] = {}
    actors_coordinates: dict[Actor, Coordinates] = {}
    flags_coordinates: dict[Flag, Coordinates] = {}
    bases_coordinates: dict[Base, Coordinates] = {}
    walls_coordinates: set[Coordinates] = set()

    def __init__(self, **kwargs: dict[str, typing.Any]) -> None:
        super().__init__(**kwargs)
        self._logger = structlog.get_logger()

        self.names_teams = {
            team["name"]: Team(name=team["name"], password=team["password"], number=i)
            for i, team in enumerate(self.teams_data)
        }
        self.teams = list(self.names_teams.values())
        self.actor_classes = [self._get_actor(actor) for actor in self.actors_data]

    def flag_is_at_home(self, team: Team) -> bool:
        flag_coordinates = next(
            coordinates
            for flag, coordinates in self.flags_coordinates.items()
            if flag.team == team
        )
        base_coordinates = next(
            coordinates
            for base, coordinates in self.bases_coordinates.items()
            if base.team == team
        )
        return flag_coordinates == base_coordinates

    @property
    def actors_of_team(self) -> dict[str, list[Actor]]:
        actors_of_team: dict[str, list[Actor]] = {}
        for team in self.teams:
            actors: list[Actor] = []
            for i in range(len(self.actor_classes)):
                actors.append(self.teams_actors[(team, i)])
            actors_of_team[team.name] = actors
        return actors_of_team

    @property
    def coordinates_actors(self) -> dict[Coordinates, Actor]:
        return {v: k for k, v in self.actors_coordinates.items()}

    @property
    def coordinates_flags(self) -> dict[Coordinates, Flag]:
        # TODO: multiple flags can be in a position! this code does not notice that
        return {v: k for k, v in self.flags_coordinates.items()}

    @property
    def coordinates_bases(self) -> dict[Coordinates, Base]:
        return {v: k for k, v in self.bases_coordinates.items()}

    def board_objects_coordinates(self, board_object: BoardObject) -> Coordinates:
        match board_object:  # pyright: ignore [reportMatchNotExhaustive]
            case Flag():
                coordinates = self.flags_coordinates[board_object]
            case Base():
                coordinates = self.bases_coordinates[board_object]
            case Actor():
                coordinates = self.actors_coordinates[board_object]
        # ignore unbound variable, if it crashes it should be fixed
        return coordinates  # pyright: ignore [reportPossiblyUnboundVariable]

    def _get_actor(self, actor: str) -> type[Actor]:
        return getattr(sys.modules[__name__], actor)

    def get_actor_properties(self) -> list[ActorProperty]:
        return [actor.get_properties() for actor in self.actor_classes]

    def get_all_objects(self, coordinates: Coordinates) -> list[BoardObject]:
        base = self.coordinates_bases.get(coordinates)
        actor = self.coordinates_actors.get(coordinates)
        flags = self.coordinates_flags.get(coordinates)
        wall = Wall() if coordinates in self.walls_coordinates else None
        objects = [base, actor, flags, wall]
        return [i for i in objects if i is not None]

    def image(self) -> str:
        field = [["___" for _ in range(self.map_size)] for _ in range(self.map_size)]

        for i, base in enumerate(self.bases_coordinates.values()):
            field[base.y][
                base.x
            ] = f" {util.colors[i]}{util.base_icon}{util.colors['revert']} "
        for actor, coordinates in self.actors_coordinates.items():
            char = actor.__class__.__name__[0].upper()
            number = actor.ident
            color = util.colors[actor.team.number]
            field[coordinates.y][
                coordinates.x
            ] = f"{color}{char}{number}{util.colors['revert']} "
        for flag, coordinates in self.flags_coordinates.items():
            color = util.colors[flag.team.number]
            before = field[coordinates.y][coordinates.x]
            field[coordinates.y][coordinates.x] = (
                before[:-2] + f" {color}{util.flag_icon}{util.colors['revert']}"
            )
        for wall_coordinate in self.walls_coordinates:
            field[wall_coordinate.y][wall_coordinate.x] = util.wall_icon
        for row in field:
            row.append("\n")
        # reverse so (0,0) is lower left not upper left
        field.reverse()
        joined = "".join(list(itertools.chain.from_iterable(field)))
        return joined
