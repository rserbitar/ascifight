import enum
import abc
import random
import itertools
import sys

from pydantic import BaseModel, ValidationError, Field
import toml
import structlog

import ascifight.util as util

with open("config.toml", mode="r") as fp:
    config = toml.load(fp)


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


class Directions(str, enum.Enum):
    left = "left"
    right = "right"
    down = "down"
    up = "up"


class Coordinates(BaseModel):
    x: int = Field(
        description="X coordinate is decreased by the 'left' and increased by the 'right' direction.",
        ge=0,
        le=config["game"]["map_size"] - 1,
    )
    y: int = Field(
        description="Y coordinate is decreased by the 'down' and increased by the 'up' direction.",
        ge=0,
        le=config["game"]["map_size"] - 1,
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
    grab = 0.0
    attack = 0.0
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
    grab = 1.0
    attack = 1.0


class Runner(Actor):
    grab = 1.0


class Attacker(Actor):
    attack = 1.0


class Blocker(Actor):
    pass


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


class Board:
    def __init__(
        self,
        teams: list[dict[str, str]] = config["teams"],
        actors: list[str] = config["game"]["actors"],
        map_size: int = config["game"]["map_size"],
        walls: int = config["game"]["walls"],
    ) -> None:
        self._logger = structlog.get_logger()

        self.map_size = map_size
        self.walls = walls

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
        actors_of_team = {}
        for team in self.teams:
            actors = []
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

    @property
    def _base_place_matrix(self):
        return [
            [[1, 4], [1, 4]],
            [[1, 4], [self.map_size - 5, self.map_size - 2]],
            [[self.map_size - 5, self.map_size - 2], [1, 4]],
            [
                [self.map_size - 5, self.map_size - 2],
                [self.map_size - 5, self.map_size - 2],
            ],
        ]

    def image(self) -> str:
        field = [["___" for _ in range(self.map_size)] for _ in range(self.map_size)]

        for i, base in enumerate(self.bases_coordinates.values()):
            field[base.y][base.x] = f" {util.colors[i]}\u25D9{util.colors['revert']} "
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
                before[:-2] + f" {color}\u25B2{util.colors['revert']}"
            )
        for wall_coordinate in self.walls_coordinates:
            field[wall_coordinate.y][wall_coordinate.x] = "\u2588\u2588\u2588"
        for row in field:
            row.append("\n")
        # reverse so (0,0) is lower left not upper left
        field.reverse()
        joined = "".join(list(itertools.chain.from_iterable(field)))
        return joined

    def get_actor_properties(self) -> list[ActorProperty]:
        return [actor.get_properties() for actor in self.actor_classes]

    def get_all_objects(self, coordinates: Coordinates) -> list[BoardObject]:
        base = self.coordinates_bases.get(coordinates)
        actor = self.coordinates_actors.get(coordinates)
        flags = self.coordinates_flags.get(coordinates)
        wall = Wall() if coordinates in self.walls_coordinates else None
        objects = [base, actor, flags, wall]
        return [i for i in objects if i is not None]

    def place_board_objects(self) -> None:
        self._place_bases_and_flags()
        for team in self.teams:
            for number, actor_class in enumerate(self.actor_classes):
                self.teams_actors[(team, number)] = actor_class(ident=number, team=team)
            coordinates = self.bases_coordinates[Base(team=team)]
            actors = [
                self.teams_actors[(team, a)] for a in range(len(self.actor_classes))
            ]
            self._place_actors(actors, coordinates)
        self._place_walls()

    def calc_target_coordinates(
        self, actor: Actor, direction: Directions
    ) -> Coordinates:
        coordinates = self.actors_coordinates[actor]
        new_coordinates = Coordinates(x=coordinates.x, y=coordinates.y)
        if direction == direction.right:
            new_coordinates.x = min(coordinates.x + 1, self.map_size - 1)
        if direction == direction.left:
            new_coordinates.x = max(coordinates.x - 1, 0)
        if direction == direction.up:
            new_coordinates.y = min(coordinates.y + 1, self.map_size - 1)
        if direction == direction.down:
            new_coordinates.y = max(coordinates.y - 1, 0)
        return new_coordinates

    def move(self, actor: Actor, direction: Directions) -> tuple[bool, None | Team]:
        team_that_scored = None
        new_coordinates = self.calc_target_coordinates(actor, direction)
        moved = self._try_put_actor(actor, new_coordinates)
        if moved:
            team_that_scored = self._check_flag_return_conditions(actor)
        return moved, team_that_scored

    def attack(self, actor: Actor, direction: Directions) -> bool:
        attacked = False
        if not actor.attack:
            self._logger.warning(f"{actor} can not attack.")
        else:
            target_coordinates = self.calc_target_coordinates(actor, direction)
            target = self.coordinates_actors.get(target_coordinates)
            if target is None:
                self._logger.warning(
                    f"No target on target coordinates {target_coordinates}."
                )
            else:
                attack_successful = random.random() < actor.attack
                if not attack_successful:
                    self._logger.info(f"{actor} attacked and missed {target}.")
                else:
                    self._logger.info(f"{actor} attacked and hit {target}.")
                    self._respawn(target)
                    attacked = True
        return attacked

    def grabput_flag(
        self, actor: Actor, direction: Directions
    ) -> tuple[bool, None | Team]:
        team_that_scored = None
        target_coordinates = self.calc_target_coordinates(actor, direction)

        grab_successful = random.random() < actor.grab
        target_actor = self.coordinates_actors.get(target_coordinates)
        already_grabbed = False
        flag: Flag | None

        if actor.flag is not None:
            flag = actor.flag

            if target_actor is not None:
                if not target_actor.grab:
                    self._logger.warning(
                        f"{actor} can not hand the flag to actor {target_actor}. Can not have the flag."
                    )

                elif target_actor.flag is not None:
                    self._logger.warning(
                        f"{actor} can not hand the flag to actor {target_actor}. Target already has a flag."
                    )

                else:
                    self.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    target_actor.flag = flag
                    already_grabbed = True
                    self._logger.info(f"{actor} handed the flag to {target_actor}.")
                    team_that_scored = self._check_flag_return_conditions(target_actor)

            # no target actor, means empty field, wall or base (even a flag???)
            else:
                if target_coordinates in self.walls_coordinates:
                    self._logger.warning(f"{actor} can not hand the flag to a wall.")

                # the flag was put on the field (maybe a base)
                else:
                    self.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    already_grabbed = True
                    self._logger.info(
                        f"{actor} put the flag to coordinates {target_coordinates}."
                    )
                    team_that_scored = self._check_score_conditions(flag)

        # the actor does not have the flag
        else:
            flag = self.coordinates_flags.get(target_coordinates)
            if flag is None:
                self._logger.warning(f"No flag at coordinates {target_coordinates}.")
            else:
                if grab_successful:
                    self.flags_coordinates[flag] = self.actors_coordinates[actor]
                    actor.flag = flag
                    already_grabbed = True

                    # and remove it from the target actor if there is one
                    if target_actor is not None:
                        target_actor.flag = None
                        self._logger.info(
                            f"{actor} grabbed the flag of {flag.team} from {target_actor}."
                        )
                    else:
                        self._logger.info(f"{actor} grabbed the flag of {flag.team}.")
                    team_that_scored = self._check_flag_return_conditions(actor=actor)
                else:
                    self._logger.info(f"{actor} grabbed and missed the flag.")

        return already_grabbed, team_that_scored

    def _get_actor(self, actor: str) -> type[Actor]:
        return getattr(sys.modules[__name__], actor)

    def _check_score_conditions(self, flag_to_score: Flag | None = None) -> Team | None:
        team_that_scored = None
        flags = (
            [flag_to_score]
            if flag_to_score
            else [flag for flag in self.flags_coordinates.keys()]
        )
        for flag_to_score in flags:
            score_flag_coordinates = self.flags_coordinates[flag_to_score]
            base_at_flag_coordinates = self.coordinates_bases.get(
                score_flag_coordinates
            )
            # if the flag is an enemy flag and owner flag is also there
            if (
                # flag is on a base
                base_at_flag_coordinates is not None
                # flag is not on it own base
                and (flag_to_score.team != base_at_flag_coordinates.team)
            ):
                scoring_team = base_at_flag_coordinates.team
                # own flag is at base or this is not required
                if (
                    self.flags_coordinates[Flag(team=scoring_team)]
                    == self.bases_coordinates[Base(team=scoring_team)]
                ) or (not config["game"]["home_flag_required"]):
                    self._logger.info(
                        f"{scoring_team} scored {flag_to_score.team} flag!"
                    )
                    team_that_scored = scoring_team
                    # return the flag to the base it belongs to

                else:
                    self._logger.warning("Can not score, flag not at home.")
        return team_that_scored

    def _respawn(self, actor: Actor) -> None:
        base_coordinates = self.bases_coordinates[Base(team=actor.team)]
        possible_spawn_points = []
        for x in range(base_coordinates.x - 2, base_coordinates.x + 3):
            for y in range(base_coordinates.y - 2, base_coordinates.y + 3):
                try:
                    possible_spawn_points.append(Coordinates(x=x, y=y))
                # ignore impossible positions
                except ValidationError:
                    pass
        actor_positions = list(self.actors_coordinates.values())
        flag_positions = list(self.flags_coordinates.values())
        base_positions = list(self.bases_coordinates.values())
        walls_positions = list(self.walls_coordinates)
        forbidden_positions = set(
            flag_positions + actor_positions + base_positions + walls_positions
        )
        self._place_actor_in_area(actor, possible_spawn_points, forbidden_positions)

    def _return_flag_to_base(self, flag: Flag) -> None:
        self.flags_coordinates[flag] = self.bases_coordinates[Base(team=flag.team)]

    def _place_bases_and_flags(self) -> None:
        available_places = list(range(len(self._base_place_matrix)))
        for team in self.teams:
            place_chosen = random.choice(available_places)
            available_places.remove(place_chosen)
            x = random.randint(*self._base_place_matrix[place_chosen][0])
            y = random.randint(*self._base_place_matrix[place_chosen][1])
            coordinates = Coordinates(x=x, y=y)
            self.bases_coordinates[Base(team=team)] = coordinates
            self.flags_coordinates[Flag(team=team)] = coordinates

    def _place_actors(self, actors: list[Actor], base: Coordinates) -> None:
        starting_places = self._get_area_positions(base, 2)
        starting_places.remove(base)
        random.shuffle(starting_places)
        starting_places = starting_places[: len(actors)]
        for actor, coordinates in zip(actors, starting_places):
            self.actors_coordinates[actor] = coordinates

    def _place_walls(self) -> None:
        forbidden_positions = set()
        for base_coordinates in self.bases_coordinates.values():
            forbidden_positions.update(self._get_area_positions(base_coordinates, 3))
        all_combinations = itertools.product(
            *[range(self.map_size), range(self.map_size)]
        )
        all_positions = {Coordinates(x=i[0], y=i[1]) for i in all_combinations}
        possible_coordinates = list(all_positions - forbidden_positions)
        random.shuffle(possible_coordinates)
        self.walls_coordinates = set(possible_coordinates[: self.walls])

    def _check_flag_return_conditions(self, actor: Actor) -> Team | None:
        team_that_scored = None
        coordinates = self.actors_coordinates[actor]
        if coordinates in self.flags_coordinates.values():
            flag = self.coordinates_flags[coordinates]
            # if flag is own flag, return it to base
            if flag.team == actor.team:
                self._return_flag_to_base(flag)
                team_that_scored = self._check_score_conditions()
                if actor.flag:
                    actor.flag = None
        return team_that_scored

    def _place_actor_in_area(
        self,
        actor: Actor,
        possible_spawn_points: list[Coordinates],
        forbidden_positions: set[Coordinates],
    ) -> None:
        allowed_positions = set(possible_spawn_points) - set(forbidden_positions)
        target_coordinates = random.choice(list(allowed_positions))
        if actor.flag is not None:
            self._logger.info(f"{actor} dropped flag {actor.flag}.")
            actor.flag = None
        self.actors_coordinates[actor] = target_coordinates
        self._logger.info(f"{actor} respawned to coordinates {target_coordinates}.")

    def _get_area_positions(
        self, center: Coordinates, distance: int
    ) -> list[Coordinates]:
        positions: list[Coordinates] = []
        for x in range(center.x - distance, center.x + distance):
            for y in range(center.y - distance, center.y + distance):
                try:
                    positions.append(Coordinates(x=x, y=y))
                    # ignore forbidden space out of bounds
                except ValidationError:
                    pass
        return positions

    def _try_put_actor(self, actor: Actor, new_coordinates: Coordinates) -> bool:
        coordinates = self.actors_coordinates[actor]
        moved = False

        if coordinates == new_coordinates:
            self._logger.warning(
                f"{actor} did not move. Target field is out of bounds."
            )
        elif self.coordinates_actors.get(new_coordinates) is not None:
            self._logger.warning(f"{actor} did not move. Target field is occupied.")
        elif self.coordinates_bases.get(new_coordinates) is not None:
            self._logger.warning(f"{actor} did not move. Target field is abase.")
        elif new_coordinates in self.walls_coordinates:
            self._logger.warning(f"{actor} did not move. Target field is a wall.")
        else:
            self.actors_coordinates[actor] = new_coordinates
            moved = True
            # move flag if actor has it
            if actor.flag is not None:
                flag = actor.flag
                self.flags_coordinates[flag] = new_coordinates

            self._logger.info(f"{actor} moved from {coordinates} to {new_coordinates}")

        return moved
