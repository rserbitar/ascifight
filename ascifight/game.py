from pydantic import BaseModel, ValidationError, Field
from typing import TypeVar
import datetime
import structlog
from structlog.contextvars import bind_contextvars, unbind_contextvars
import enum
import itertools
import random
import abc
import toml
import sys


with open("config.toml", mode="r") as fp:
    config = toml.load(fp)

colors = {
    0: "\u001b[31m",
    1: "\u001b[32m",
    2: "\u001b[33m",
    3: "\u001b[34m",
    4: "\u001b[35m",
    5: "\u001b[36m",
    "bold": "\033[1m",
    "revert": "\x1b[0m",
}

T = TypeVar("T")


class Directions(str, enum.Enum):
    left = "left"
    right = "right"
    down = "down"
    up = "up"


class Order(BaseModel):
    team: str = Field(description="Name of the team to issue the order.")
    password: str = Field(
        description="The password for the team used during registering."
    )

    def __str__(self):
        return f"Order by {self.team}"


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


class AttackOrder(Order):
    actor: int = Field(
        description="The id of the actor, specific to the team.",
        ge=0,
        le=len(config["game"]["actors"]) - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description="The direction to attack from the position of the actor.",
    )

    def __str__(self):
        return f"AttackOrder by Actor {self.team}-{self.actor} -> {self.direction}"


class MoveOrder(Order):
    actor: int = Field(
        description="The id of the actor, specific to the team.",
        ge=0,
        le=len(config["game"]["actors"]) - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description="The direction to move to from the position of the actor. 'up' increases the y coordinate and 'right' increases the x coordinate.",
    )

    def __str__(self):
        return f"MoveOrder by Actor {self.team}-{self.actor} -> {self.direction}"


class GrabPutOrder(Order):
    actor: int = Field(
        title="Actor",
        description="The id of the actor, specific to the team.",
        ge=0,
        le=len(config["game"]["actors"]) - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description=(
            "The direction to grab of put the flag from the position of the actor. "
        ),
    )

    def __str__(self):
        return f"GrabPutOrder by Actor {self.team}-{self.actor} -> {self.direction}"


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
    def __init__(self, walls=0) -> None:
        self.logger = structlog.get_logger()
        self.map_size = config["game"]["map_size"]
        self.walls = walls

        self.logger = structlog.get_logger()
        self.actors_coordinates: dict[Actor, Coordinates] = {}
        self.flags_coordinates: dict[Flag, Coordinates] = {}
        self.bases_coordinates: dict[Base, Coordinates] = {}
        self.walls_coordinates: set[Coordinates] = set()

    @property
    def base_place_matrix(self):
        return [
            [[1, 4], [1, 4]],
            [[1, 4], [self.map_size - 5, self.map_size - 2]],
            [[self.map_size - 5, self.map_size - 2], [1, 4]],
            [
                [self.map_size - 5, self.map_size - 2],
                [self.map_size - 5, self.map_size - 2],
            ],
        ]

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

    def get_all_objects(self, coordinates) -> list[BoardObject]:
        base = self.coordinates_bases.get(coordinates)
        actor = self.coordinates_actors.get(coordinates)
        flags = self.coordinates_flags.get(coordinates)
        wall = Wall() if coordinates in self.walls_coordinates else None
        objects = [base, actor, flags, wall]
        return [i for i in objects if i is not None]

    def respawn(self, actor: Actor) -> None:
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

    def return_flag_to_base(self, flag: Flag) -> None:
        self.flags_coordinates[flag] = self.bases_coordinates[Base(team=flag.team)]

    def place_bases_and_flags(self, teams: list[Team]) -> None:
        available_places = list(range(len(self.base_place_matrix)))
        for team in teams:
            place_chosen = random.choice(available_places)
            available_places.remove(place_chosen)
            x = random.randint(*self.base_place_matrix[place_chosen][0])
            y = random.randint(*self.base_place_matrix[place_chosen][1])
            coordinates = Coordinates(x=x, y=y)
            self.bases_coordinates[Base(team=team)] = coordinates
            self.flags_coordinates[Flag(team=team)] = coordinates

    def place_actors(self, actors: list[Actor], base: Coordinates) -> None:
        starting_places = self._get_area_positions(base, 2)
        starting_places.remove(base)
        random.shuffle(starting_places)
        starting_places = starting_places[: len(actors)]
        for actor, coordinates in zip(actors, starting_places):
            self.actors_coordinates[actor] = coordinates

    def place_walls(self) -> None:
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

    def move(self, actor: Actor, direction: Directions) -> bool:
        new_coordinates = self.calc_target_coordinates(actor, direction)
        return self._try_put_actor(actor, new_coordinates)

    def image(self) -> str:
        field = [["___" for _ in range(self.map_size)] for _ in range(self.map_size)]

        for i, base in enumerate(self.bases_coordinates.values()):
            field[base.y][base.x] = f" {colors[i]}\u25D9{colors['revert']} "
        for actor, coordinates in self.actors_coordinates.items():
            char = actor.__class__.__name__[0].upper()
            number = actor.ident
            color = colors[actor.team.number]
            field[coordinates.y][
                coordinates.x
            ] = f"{color}{char}{number}{colors['revert']} "
        for flag, coordinates in self.flags_coordinates.items():
            color = colors[flag.team.number]
            before = field[coordinates.y][coordinates.x]
            field[coordinates.y][coordinates.x] = (
                before[:-2] + f" {color}\u25B2{colors['revert']}"
            )
        for wall_coordinate in self.walls_coordinates:
            field[wall_coordinate.y][wall_coordinate.x] = "\u2588\u2588\u2588"
        for row in field:
            row.append("\n")
        # reverse so (0,0) is lower left not upper left
        field.reverse()
        joined = "".join(list(itertools.chain.from_iterable(field)))
        return joined

    def _place_actor_in_area(
        self,
        actor: Actor,
        possible_spawn_points: list[Coordinates],
        forbidden_positions: set[Coordinates],
    ) -> None:
        allowed_positions = set(possible_spawn_points) - set(forbidden_positions)
        target_coordinates = random.choice(list(allowed_positions))
        if actor.flag is not None:
            self.logger.info(f"{actor} dropped flag {actor.flag}.")
            actor.flag = None
        self.actors_coordinates[actor] = target_coordinates
        self.logger.info(f"{actor} respawned to coordinates {target_coordinates}.")

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
            self.logger.warning(f"{actor} did not move. Target field is out of bounds.")
        elif self.coordinates_actors.get(new_coordinates) is not None:
            self.logger.warning(f"{actor} did not move. Target field is occupied.")
        elif self.coordinates_bases.get(new_coordinates) is not None:
            self.logger.warning(f"{actor} did not move. Target field is abase.")
        elif new_coordinates in self.walls_coordinates:
            self.logger.warning(f"{actor} did not move. Target field is a wall.")
        else:
            self.actors_coordinates[actor] = new_coordinates
            moved = True
            # move flag if actor has it
            if actor.flag is not None:
                flag = actor.flag
                self.flags_coordinates[flag] = new_coordinates

            self.logger.info(f"{actor} moved from {coordinates} to {new_coordinates}")

        return moved


class Game:
    def __init__(
        self,
        board: Board,
        teams: list[dict[str, str]] = config["teams"],
        actors: list[str] = config["game"]["actors"],
        score_file=config["server"]["scores_file"],
        score_multiplier: int = config["game"]["score_multiplier"],
        max_ticks: int = config["game"]["max_ticks"],
        max_score: int = config["game"]["max_score"],
    ) -> None:
        self.logger = structlog.get_logger()
        self.score_file = score_file
        self.score_multiplier = score_multiplier
        self.actors: list[type[Actor]] = [self._get_actor(actor) for actor in actors]
        self.board = board
        self.teams: list[str] = [team["name"] for team in teams]
        self.names_teams: dict[str, Team] = {
            team["name"]: Team(name=team["name"], password=team["password"], number=i)
            for i, team in enumerate(teams)
        }
        self.teams_actors: dict[tuple[Team, int], Actor] = {}
        self.scores: dict[Team, int] = {}
        self.overall_score: dict[Team, int] = {}
        self.tick = 0
        self.max_ticks = max_ticks
        self.max_score = max_score

    @property
    def actors_of_team(self) -> dict[str, list[Actor]]:
        actors_of_team = {}
        for team in self.names_teams.values():
            actors = []
            for i in range(len(self.actors)):
                actors.append(self.teams_actors[(team, i)])
            actors_of_team[team.name] = actors
        return actors_of_team

    def initiate_game(self) -> None:
        self._set_scores()
        self._read_scores()
        self._create_team_actors()
        self._place_board_objects()

    def end_game(self):
        self._write_scores()

    def execute_game_step(self, orders: list[Order]) -> None:
        self.tick += 1

        move_orders: list[MoveOrder] = []
        attack_orders: list[AttackOrder] = []
        grabput_orders: list[GrabPutOrder] = []

        for order in orders:
            if self._validate_order(order):
                if isinstance(order, MoveOrder):
                    move_orders.append(order)
                elif isinstance(order, AttackOrder):
                    attack_orders.append(order)
                elif isinstance(order, GrabPutOrder):
                    grabput_orders.append(order)

        self.logger.info("Executing move orders.")
        self._execute_move_orders(move_orders)

        self.logger.info("Executing grab/put orders.")
        self._execute_grabput_orders(grabput_orders)

        self.logger.info("Executing attack orders.")
        self._execute_attack_orders(attack_orders)

    def scoreboard(self) -> str:
        current_score = " - ".join(
            [
                f"{colors[team.number]}{team.name}: {score}{colors['revert']}"
                for team, score in self.scores.items()
            ]
        )
        overall_score = " - ".join(
            [
                f"{colors[team.number]}{team.name}: {score}{colors['revert']}"
                for team, score in self.overall_score.items()
            ]
        )
        return f"{colors['bold']}Overall Score{colors['revert']}: {overall_score} \n{colors['bold']}Current Score{colors['revert']}: {current_score}"

    def get_actor_properties(self) -> list[ActorProperty]:
        return [actor.get_properties() for actor in self.actors]

    def _get_actor(self, actor: str) -> type[Actor]:
        return getattr(sys.modules[__name__], actor)

    def _set_scores(self) -> None:
        for team in self.names_teams.values():
            self.scores[team] = 0
            self.overall_score[team] = 0

    def _write_scores(self):
        game_scores = []
        scores = list(self.scores.items())
        scores = sorted(scores, key=lambda x: x[1], reverse=True)
        if scores[0][1] == scores[1][1]:
            tied_teams = [team for team, value in scores if value == scores[0][1]]
            game_scores = [(team, 1 * self.score_multiplier) for team in tied_teams]
        else:
            game_scores = [(scores[0][0], 3 * self.score_multiplier)]

        with open(self.score_file, "a") as score_file:
            for score in game_scores:
                score_file.write(f"{score[0].name}: {score[1]}\n")

    def _read_scores(self):
        try:
            with open(self.score_file, "r") as score_file:
                for line in score_file:
                    team, score = line.split(":")
                    score = int(score)
                    team = team.strip()
                    try:
                        self.overall_score[self.names_teams[team]] += score
                    # ignore score if team is not in current teams
                    except ValueError:
                        pass
        # if the file is not yet there assume default scores
        except FileNotFoundError:
            pass

    def _place_board_objects(self) -> None:
        self.board.place_bases_and_flags(list(self.names_teams.values()))
        for team in self.names_teams.values():
            coordinates = self.board.bases_coordinates[Base(team=team)]
            actors = [self.teams_actors[(team, a)] for a in range(len(self.actors))]
            self.board.place_actors(actors, coordinates)
        self.board.place_walls()

    def _create_team_actors(self) -> None:
        for team in self.names_teams.values():
            for number, actor in enumerate(self.actors):
                self.teams_actors[(team, number)] = actor(ident=number, team=team)

    def _actor_dict(self, value: T) -> dict[Actor, T]:
        value_dict = {}
        for actor in self.teams_actors.values():
            value_dict[actor] = value
        return value_dict

    def _validate_order(self, order: Order) -> bool:
        check = False
        if order.team in self.names_teams.keys():
            check = self.names_teams[order.team].password == order.password
            if not check:
                self.logger.warning(f"{order} was ignored. Wrong password.")
        else:
            self.logger.warning(f"{order} was ignored. Team unknown.")
        return check

    def _execute_move_orders(self, move_orders: list[MoveOrder]) -> None:
        already_moved = self._actor_dict(False)
        for order in move_orders:
            bind_contextvars(team=order.team)
            self.logger.info(f"Executing {order}")
            actor = self.teams_actors[(self.names_teams[order.team], order.actor)]
            direction = order.direction
            if already_moved[actor]:
                self.logger.warning(f"{actor} already moved this tick.")
            else:
                # if the actor can move
                already_moved[actor] = self.board.move(actor, direction)
                if already_moved[actor]:
                    self._check_flag_return_conditions(actor)

        unbind_contextvars("team")

    def _execute_attack_orders(self, attack_orders: list[AttackOrder]) -> None:
        already_attacked = self._actor_dict(False)
        for order in attack_orders:
            bind_contextvars(team=order.team)
            self.logger.info(f"Executing {order}")
            actor = self.teams_actors[(self.names_teams[order.team], order.actor)]
            attack_successful = random.random() < actor.attack

            if already_attacked[actor]:
                self.logger.warning(f"{actor} already attacked this tick.")
            else:
                if not actor.attack:
                    self.logger.warning(f"{actor} can not attack.")
                else:
                    direction = order.direction
                    target_coordinates = self.board.calc_target_coordinates(
                        actor, direction
                    )
                    target = self.board.coordinates_actors.get(target_coordinates)
                    if target is None:
                        self.logger.warning(
                            f"No target on target coordinates {target_coordinates}."
                        )
                    else:
                        if not attack_successful:
                            self.logger.info(f"{actor} attacked and missed {target}.")
                        else:
                            self.logger.info(f"{actor} attacked and hit {target}.")
                            self.board.respawn(target)
                            already_attacked[actor] = True

        unbind_contextvars("team")

    def _execute_grabput_orders(self, grabput_orders: list[GrabPutOrder]):
        already_grabbed = self._actor_dict(False)
        for order in grabput_orders:
            bind_contextvars(team=order.team)
            self.logger.info(f"Executing {order}")
            actor = self.teams_actors[(self.names_teams[order.team], order.actor)]
            if not already_grabbed[actor]:
                target_coordinates = self.board.calc_target_coordinates(
                    actor, order.direction
                )

                already_grabbed[actor] = self._grabput_flag(actor, target_coordinates)
            else:
                self.logger.warning(f"{actor} already grabbed this tick.")
        unbind_contextvars("team")

    def _grabput_flag(self, actor: Actor, target_coordinates: Coordinates) -> bool:
        grab_successful = random.random() < actor.grab
        target_actor = self.board.coordinates_actors.get(target_coordinates)
        already_grabbed = False
        flag: Flag | None

        if actor.flag is not None:
            flag = actor.flag

            if target_actor is not None:
                if not target_actor.grab:
                    self.logger.warning(
                        f"{actor} can not hand the flag to actor {target_actor}. Can not have the flag."
                    )

                elif target_actor.flag is not None:
                    self.logger.warning(
                        f"{actor} can not hand the flag to actor {target_actor}. Target already has a flag."
                    )

                else:
                    self.board.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    target_actor.flag = flag
                    already_grabbed = True
                    self.logger.info(f"{actor} handed the flag to {target_actor}.")
                    self._check_flag_return_conditions(target_actor)

            # no target actor, means empty field, wall or base (even a flag???)
            else:
                if target_coordinates in self.board.walls_coordinates:
                    self.logger.warning(f"{actor} can not hand the flag to a wall.")

                # the flag was put on the field (maybe a base)
                else:
                    self.board.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    already_grabbed = True
                    self.logger.info(
                        f"{actor} put the flag to coordinates {target_coordinates}."
                    )
                    self._check_score_conditions(flag)

        # the actor does not have the flag
        else:
            flag = self.board.coordinates_flags.get(target_coordinates)
            if flag is None:
                self.logger.warning(f"No flag at coordinates {target_coordinates}.")
            else:
                if grab_successful:
                    self.board.flags_coordinates[flag] = self.board.actors_coordinates[
                        actor
                    ]
                    actor.flag = flag
                    already_grabbed = True

                    # and remove it from the target actor if there is one
                    if target_actor is not None:
                        target_actor.flag = None
                        self.logger.info(
                            f"{actor} grabbed the flag of {flag.team} from {target_actor}."
                        )
                    else:
                        self.logger.info(f"{actor} grabbed the flag of {flag.team}.")
                    self._check_flag_return_conditions(actor=actor)
                else:
                    self.logger.info(f"{actor} grabbed and missed the flag.")

        return already_grabbed

    def check_game_end(self):
        return (
            self.tick == self.max_ticks or max(self.scores.values()) == self.max_score
        )

    def _check_score_conditions(self, flag_to_score: Flag | None = None) -> None:
        flags = (
            [flag_to_score]
            if flag_to_score
            else [flag for flag in self.board.flags_coordinates.keys()]
        )
        for flag_to_score in flags:
            score_flag_coordinates = self.board.flags_coordinates[flag_to_score]
            base_at_flag_coordinates = self.board.coordinates_bases.get(
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
                    self.board.flags_coordinates[Flag(team=scoring_team)]
                    == self.board.bases_coordinates[Base(team=scoring_team)]
                ) or (not config["game"]["home_flag_required"]):
                    self.logger.info(
                        f"{scoring_team} scored {flag_to_score.team} flag!"
                    )
                    self.scores[scoring_team] += 1
                    # return the flag to the base it belongs to

                else:
                    self.logger.warning("Can not score, flag not at home.")

    def _check_flag_return_conditions(self, actor: Actor) -> None:
        coordinates = self.board.actors_coordinates[actor]
        if coordinates in self.board.flags_coordinates.values():
            flag = self.board.coordinates_flags[coordinates]
            # if flag is own flag, return it to base
            if flag.team == actor.team:
                self.board.return_flag_to_base(flag)
                self._check_score_conditions()
                if actor.flag:
                    actor.flag = None
