from pydantic import BaseModel, ValidationError, Field
from typing import TypeVar
import datetime
import structlog
import enum
import itertools
import random
import abc

MAP_SIZE = 15
MAX_SCORE = 3
MAX_TICKS = 200
ACTORNUM = 1


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
    team: str = Field(decription="Name of the team to issue the order.")
    password: str = Field(
        decscription="The password for the team used during registering."
    )


class Coordinates(BaseModel):
    x: int = Field(
        description="X coodinate is decreased by the 'left' and increased by the 'right' direction.",
        ge=0,
        le=MAP_SIZE - 1,
    )
    y: int = Field(
        description="Y coodinate is decreased by the 'down' and increased by the 'up' direction.",
        ge=0,
        le=MAP_SIZE - 1,
    )

    def __eq__(self, another):
        return (
            hasattr(another, "x")
            and self.x == another.x
            and hasattr(another, "y")
            and self.y == another.y
        )

    def __hash__(self):
        return hash((self.x, self.y))


class AttackOrder(Order):
    actor: int = Field(
        description="The id of the actor, specific to the team.",
        ge=0,
        le=ACTORNUM - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description="The direction to attack from the position of the actor.",
    )


class MoveOrder(Order):
    actor: int = Field(
        description="The id of the actor, specific to the team.",
        ge=0,
        le=ACTORNUM - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description="The direction to move to from the position of the actor. 'up' increases the y coordinate and 'right' increases the x coordinate.",
    )


class GrabPutOrder(Order):
    actor: int = Field(
        title="Actor",
        description="The id of the actor, specific to the team.",
        ge=0,
        le=ACTORNUM - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description=(
            "The direction to grap of put the flag from the position of the actor. "
        ),
    )


class Team(BaseModel):
    name: str
    password: str
    number: int

    def __eq__(self, another):
        return hasattr(another, "name") and self.name == another.name

    def __hash__(self):
        return hash(self.name)


class Actor(BaseModel, abc.ABC):
    type = "Base"
    ident: int
    team: Team
    grab = 0.0
    attack = 0.0
    flag: int | None = None

    def __eq__(self, another):
        return (
            hasattr(another, "ident")
            and self.ident == another.ident
            and hasattr(another, "team")
            and self.team == another.team
        )

    def __hash__(self):
        return hash((self.ident, self.team))


class Generalist(Actor):
    type = "Generalist"
    grab = 1.0
    attack = 1.0


class Runner(Actor):
    type = "Runner"
    grab = 1.0


class Attacker(Actor):
    type = "Attacker"
    attack = 1.0


class Blocker(Actor):
    type = "Blocker"


class InitialActorsList(BaseModel):
    actors: list[type[Actor]] = Field(min_items=ACTORNUM, max_items=ACTORNUM)


class Board:
    def __init__(self, map_size: int, walls=0) -> None:
        self.logger = structlog.get_logger()
        self.map_size = map_size
        self.walls = walls

        self.logger = logger = structlog.get_logger()
        self.actors_coordinates: dict[Actor, Coordinates] = {}
        self.flags_coordinates: dict[int, Coordinates] = {}
        self.bases_coordinates: dict[int, Coordinates] = {}
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
    def coordinates_flags(self) -> dict[Coordinates, int]:
        return {v: k for k, v in self.flags_coordinates.items()}

    @property
    def coordinates_bases(self) -> dict[Coordinates, int]:
        return {v: k for k, v in self.bases_coordinates.items()}

    def respawn(self, actor: Actor) -> None:
        base_coordinates = self.flags_coordinates[actor.team.number]
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
        self.place_actor_in_area(actor, possible_spawn_points, forbidden_positions)

    def place_actor_in_area(
        self,
        actor: Actor,
        possible_spawn_points: list[Coordinates],
        forbidden_positions: set[Coordinates],
    ) -> None:
        while True:
            target_coordinates = random.choice(possible_spawn_points)
            if target_coordinates not in forbidden_positions:
                if actor.flag is not None:
                    self.logger.info(
                        f"Actor {actor.team.name}-{actor.ident} dropped flag {actor.flag}."
                    )
                    actor.flag = None
                self.actors_coordinates[actor] = target_coordinates
                self.logger.info(
                    f"Actor {actor.team.name}-{actor.ident} respawned to coordinates {target_coordinates}."
                )
                break

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
        return self.try_put_actor(actor, new_coordinates)

    def try_put_actor(self, actor: Actor, new_coordinates: Coordinates) -> bool:
        coordinates = self.actors_coordinates[actor]

        # check if position is already inhabited by an actor or base or wall
        if (
            self.coordinates_actors.get(new_coordinates)
            or self.coordinates_bases.get(new_coordinates)
            or new_coordinates in self.walls_coordinates
        ):
            self.logger.info(
                f"Actor {actor.team.name}-{actor.ident} did not move. Target field is occupied or out of bounds."
            )
            return False

        self.actors_coordinates[actor] = new_coordinates
        # move flag if actor has it
        if actor.flag is not None:
            flag = actor.flag
            self.flags_coordinates[flag] = new_coordinates

        self.logger.info(
            f"Actor {actor.team.name}-{actor.ident} moved from ({coordinates}) to ({new_coordinates})"
        )
        return True

    def image(self) -> str:
        field = [["___" for _ in range(self.map_size)] for _ in range(self.map_size)]

        for i, base in enumerate(self.bases_coordinates.values()):
            field[base.y][base.x] = f" {colors[i]}\u25D9{colors['revert']} "
        for actor, coordinates in self.actors_coordinates.items():
            char = actor.type[0].upper()
            color = colors[actor.team.number]
            field[coordinates.y][coordinates.x] = f" {color}{char}{colors['revert']} "
        for flag, coordinates in self.flags_coordinates.items():
            color = colors[flag]
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

    def place_bases(self, teams: int) -> None:
        available_places = list(range(len(self.base_place_matrix)))
        for i in range(teams):
            place_chosen = random.choice(available_places)
            available_places.remove(place_chosen)
            x = random.randint(*self.base_place_matrix[place_chosen][0])
            y = random.randint(*self.base_place_matrix[place_chosen][1])
            coordinates = Coordinates(x=x, y=y)
            self.bases_coordinates[i] = coordinates
            self.flags_coordinates[i] = coordinates

    def reserve_space(self, taken, coordinates):
        for x in range(coordinates.x - 2, coordinates.x + 3):
            for y in range(coordinates.y - 2, coordinates.y + 3):
                taken.append(Coordinates(x=x, y=y))
        return taken

    def place_actors(self, actors: list[Actor], base: Coordinates) -> None:
        starting_places = []
        for x in range(base.x - 1, base.x + 2):
            for y in range(base.y - 1, base.y + 2):
                starting_places.append(Coordinates(x=x, y=y))
        starting_places.remove(base)
        starting_places = starting_places[: len(actors)]
        for actor, coordinates in zip(actors, starting_places):
            self.actors_coordinates[actor] = coordinates

    def place_walls(self) -> None:
        forbidden_postions = set()
        for base_coordinates in self.bases_coordinates.values():
            for x in range(base_coordinates.x - 2, base_coordinates.x + 3):
                for y in range(base_coordinates.y - 2, base_coordinates.y + 3):
                    try:
                        forbidden_postions.add(Coordinates(x=x, y=y))
                    # ignore forbidden space out of bounds
                    except ValidationError:
                        pass
        walls = 0
        while walls < self.walls:
            coordinates = Coordinates(
                x=random.randint(0, self.map_size - 1),
                y=random.randint(0, self.map_size - 1),
            )
            if coordinates not in forbidden_postions:
                self.walls_coordinates.add(coordinates)
                walls += 1


class Game:
    def __init__(
        self,
        pregame_wait: int,
        board: Board,
        teams: list[Team],
        actors: InitialActorsList,
    ) -> None:
        self.logger = structlog.get_logger()

        self.actors = actors.actors
        self.board = board
        self.teams: list[str] = [team.name for team in teams]
        self.names_teams: dict[str, Team] = {team.name: team for team in teams}
        self.teams_actors: dict[tuple[Team, int], Actor] = {}
        self.scores: dict[int, int] = {}

        self.time_of_next_execution = datetime.datetime.now()
        self.pregame_wait = pregame_wait
        self.tick = 0

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
        self.set_scores()
        self.create_team_actors()
        self.place_actors_and_bases()

    def set_scores(self) -> None:
        for i in range(len(self.names_teams)):
            self.scores[i] = 0

    def scoreboard(self) -> str:
        return " - ".join(
            [
                f"{colors[i]}{name}: {score}{colors['revert']}"
                for i, (name, score) in enumerate(zip(self.teams, self.scores.values()))
            ]
        )

    def place_actors_and_bases(self) -> None:
        self.board.place_bases(len(self.names_teams))
        for p, team in enumerate(self.names_teams.values()):
            coordinates = self.board.bases_coordinates[p]
            actors = []
            for a in range(len(self.actors)):
                actors.append(self.teams_actors[(team, a)])
                self.board.place_actors(actors, coordinates)
        self.board.place_walls()

    def create_team_actors(self) -> None:
        for team in self.names_teams.values():
            for number, actor in enumerate(self.actors):
                self.teams_actors[(team, number)] = actor(ident=number, team=team)

    def actor_dict(self, value: T) -> dict[Actor, T]:
        value_dict = {}
        for actor in self.teams_actors.values():
            value_dict[actor] = value
        return value_dict

    def validate_order(self, order: Order) -> bool:
        check = False
        if order.team in self.names_teams.keys():
            check = self.names_teams[order.team].password == order.password
            if not check:
                self.logger.warning(
                    f"Order {type(Order)} from team {Order.team} was ignored. Wrong password."
                )
        else:
            self.logger.warning(
                f"Order {type(Order)} from team {Order.team} was ignored. Team unknown."
            )
        return check

    def execute_gamestep(self, orders: list[Order]) -> None:
        self.tick += 1

        move_orders: list[MoveOrder] = []
        attack_orders: list[AttackOrder] = []
        grabput_orders: list[GrabPutOrder] = []

        for order in orders:
            if self.validate_order(order):
                if isinstance(order, MoveOrder):
                    move_orders.append(order)
                elif isinstance(order, AttackOrder):
                    attack_orders.append(order)
                elif isinstance(order, GrabPutOrder):
                    grabput_orders.append(order)

        self.logger.info("Executing move orders.")
        self.execute_move_orders(move_orders)

        self.logger.info("Executing grab/put orders.")
        self.execute_grabput_orders(grabput_orders)

        self.logger.info("Executing attack orders.")
        self.execute_attack_orders(attack_orders)

    def execute_move_orders(self, move_orders: list[MoveOrder]) -> None:
        already_moved = self.actor_dict(False)
        for order in move_orders:
            actor = self.teams_actors[(self.names_teams[order.team], order.actor)]
            direction = order.direction
            if not already_moved[actor]:
                # if the actor can move
                already_moved[actor] = self.board.move(actor, direction)
                if already_moved[actor]:
                    self.check_flag_return_conditions(actor)

    def execute_attack_orders(self, attack_orders: list[AttackOrder]) -> None:
        already_attacked = self.actor_dict(False)
        for order in attack_orders:
            actor = self.teams_actors[(self.names_teams[order.team], order.actor)]

            # if the actor can not attack or the attack missed or it aldready attacked
            if (attack_roll := random.random() < actor.attack) and (
                not already_attacked[actor]
            ):
                direction = order.direction
                target_coordinates = self.board.calc_target_coordinates(
                    actor, direction
                )
                target = self.board.coordinates_actors.get(target_coordinates)
                if target is not None:
                    self.logger.info(
                        f"Actor {actor.team.name}-{actor.ident} attacked and hit actor {target.team.name}-{target.ident}."
                    )
                    self.board.respawn(target)
                    already_attacked[actor] = True

            else:
                self.logger.info(
                    f"Actor {actor.team.name}-{actor.ident} did not attack. Actor can not attack or missed."
                )

    def execute_grabput_orders(self, grabput_orders: list[GrabPutOrder]):
        already_grabbed = self.actor_dict(False)
        for order in grabput_orders:
            actor = self.teams_actors[(self.names_teams[order.team], order.actor)]
            if (grab_roll := random.random() < actor.grab) and (
                not already_grabbed[actor]
            ):
                target_coordinates = self.board.calc_target_coordinates(
                    actor, order.direction
                )

                already_grabbed[actor] = self.grabput_flag(actor, target_coordinates)

    def grabput_flag(self, actor: Actor, target_coordinates: Coordinates) -> bool:
        target_actor = self.board.coordinates_actors.get(target_coordinates)
        already_grabbed = True
        # the actor does have the flag
        if actor.flag is not None:
            flag = actor.flag

            # if there is a target actor
            if target_actor is not None:
                # target actor can not have the glag
                if not target_actor.grab:
                    already_grabbed = False
                    self.logger.warning(
                        f"Actor {actor.team.name}-{actor.ident} can not hand the flag to actor {target_actor.team.name}-{target_actor.ident}. Can not have the flag."
                    )
                # target actor has the flag
                elif target_actor.flag is not None:
                    already_grabbed = False
                    self.logger.warning(
                        f"Actor {actor.team.name}-{actor.ident} can not hand the flag to actor {target_actor.team.name}-{target_actor.ident}. Target already has a flag."
                    )
                #
                else:
                    self.board.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    target_actor.flag = flag
                    self.logger.info(
                        f"Actor {actor.team.name}-{actor.ident} handed the flag to actor {target_actor.team.name}-{target_actor.ident}."
                    )
                    self.check_flag_return_conditions(target_actor)
            # no target actor, means empty field, wall or base (even a flag???)
            else:
                # if the target coordinates are a wall
                if target_coordinates in self.board.walls_coordinates:
                    already_grabbed = False
                    self.logger.warning(
                        f"Actor {actor.team.name}-{actor.ident} can not hand the flag to a wall."
                    )

                # the flag was put on the field (maybe a base)
                else:
                    self.board.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    self.logger.info(
                        f"Actor {actor.team.name}-{actor.ident} put the flag to coordinates {target_coordinates}."
                    )
                    self.check_score_conditions(flag)

        # the actor does not have the flag
        else:
            # if the flag is at the target coordinates, grab it
            if flag := self.board.coordinates_flags.get(target_coordinates) is not None:
                self.board.flags_coordinates[flag] = self.board.actors_coordinates[
                    actor
                ]
                actor.flag = flag

                # and remove it from the target actor if there is one
                if target_actor is not None:
                    target_actor.flag = None

            # if there is no flag at the destionation, do nothing
            else:
                already_grabbed = False

        return already_grabbed

    def check_score_conditions(self, flag: int) -> None:
        coordinates = self.board.flags_coordinates[flag]
        if coordinates in self.board.bases_coordinates.values():
            base = self.board.coordinates_bases[coordinates]
            # if flag is not standing on own base but another
            if base != flag:
                self.logger.info(
                    f"Team {self.teams[base]} scored {self.teams[flag]} flag!"
                )
                self.scores[base] += 1
                self.board.flags_coordinates[flag] = self.board.bases_coordinates[flag]

    def check_flag_return_conditions(self, actor: Actor) -> None:
        coordinates = self.board.actors_coordinates[actor]
        if coordinates in self.board.flags_coordinates.values():
            flag = self.board.coordinates_flags[coordinates]
            # if flag is own flag, return it to base
            if flag == actor.team.number:
                self.board.flags_coordinates[flag] = self.board.bases_coordinates[flag]
