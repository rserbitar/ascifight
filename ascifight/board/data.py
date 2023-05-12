import abc
import sys
import itertools
import os
import typing

from pydantic import BaseModel, Field
import toml
import structlog

import ascifight.config as config
import ascifight.util as util


class Team(BaseModel):
    name: str
    password: str
    number: int

    def __eq__(self, another):
        return hasattr(another, "name") and self.name == another.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return f"Team {self.name}"


class Coordinates(BaseModel):
    x: int = Field(
        description="X coordinate is decreased by the 'left' and increased by the 'right' direction.",
        ge=0,
        le=config.config["game"]["map_size"] - 1,
    )
    y: int = Field(
        description="Y coordinate is decreased by the 'down' and increased by the 'up' direction.",
        ge=0,
        le=config.config["game"]["map_size"] - 1,
    )

    def __str__(self) -> str:
        return f"({self.x}/{self.y})"

    def __eq__(self, another):
        return (
            hasattr(another, "x")
            and self.x == another.x
            and hasattr(another, "y")
            and self.y == another.y
        )

    def __hash__(self) -> int:
        return hash((self.x, self.y))


class ActorProperty(BaseModel):
    type: str
    grab: float = Field(
        description="The probability to successfully grab or put the flag. "
        "An actor with 0 can not carry the flag. Not even when it is given to it.",
    )
    attack: float = Field(
        description="The probability to successfully attack. An actor with 0 can not attack.",
    )


class BoardObject(BaseModel, abc.ABC):
    pass


class Flag(BoardObject):
    team: Team

    def __eq__(self, another):
        return (
            self.__class__.__name__ == another.__class__.__name__
            and hasattr(another, "team")
            and self.team.name == another.team.name
        )

    def __hash__(self):
        return hash((self.__class__.__name__, self.team.name))


class Actor(BoardObject, abc.ABC):
    ident: int
    team: Team
    grab: typing.ClassVar[float] = 0.0
    attack: typing.ClassVar[float] = 0.0
    build: typing.ClassVar[float] = 0.0
    destroy: typing.ClassVar[float] = 0.0
    flag: Flag | None = None

    def __str__(self):
        return f"Actor ({self.__class__.__name__}) {self.team}-{self.ident}"

    def __eq__(self, another):
        return (
            self.__class__.__name__ == another.__class__.__name__
            and hasattr(another, "ident")
            and self.ident == another.ident
            and hasattr(another, "team")
            and self.team == another.team
        )

    def __hash__(self):
        return hash((self.__class__.__name__, self.ident, self.team))

    @classmethod
    def get_properties(cls) -> ActorProperty:
        return ActorProperty(type=cls.__name__, grab=cls.grab, attack=cls.attack)


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

    def __eq__(self, another):
        return (
            self.__class__.__name__ == another.__class__.__name__
            and hasattr(another, "team")
            and self.team.name == another.team.name
        )

    def __hash__(self):
        return hash((self.__class__.__name__, self.team.name))


class Wall(BoardObject):
    pass


class BoardData:
    def __init__(
        self,
        teams: list[dict[str, str]] = config.config["teams"],
        actors: list[str] = config.config["game"]["actors"],
        map_size: int = config.config["game"]["map_size"],
        walls: int = config.config["game"]["walls"],
    ) -> None:
        self._logger = structlog.get_logger()

        self.map_size: int = map_size
        self.walls: int = walls

        self.names_teams: dict[str, Team] = {
            team["name"]: Team(name=team["name"], password=team["password"], number=i)
            for i, team in enumerate(teams)
        }
        self.teams: list[Team] = list(self.names_teams.values())
        self.actor_classes: list[type[Actor]] = [
            self._get_actor(actor) for actor in actors
        ]
        self.teams_actors: dict[tuple[Team, int], Actor] = {}
        self.actors_coordinates: dict[Actor, Coordinates] = {}
        self.flags_coordinates: dict[Flag, Coordinates] = {}
        self.bases_coordinates: dict[Base, Coordinates] = {}
        self.walls_coordinates: set[Coordinates] = set()

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
        match board_object:
            case Flag():
                coordinates = self.flags_coordinates[board_object]
            case Base():
                coordinates = self.bases_coordinates[board_object]
            case Actor():
                coordinates = self.actors_coordinates[board_object]
        # ignore unbound variable, if it crashes it should be fixed
        return coordinates  # type: ignore

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
