from fastapi import FastAPI
from pydantic import BaseModel, validator, ValidationError, Field
from collections import defaultdict
from typing import TypeVar, cast
import structlog
from structlog.contextvars import (
    bind_contextvars,
    bound_contextvars,
    clear_contextvars,
    merge_contextvars,
    unbind_contextvars,
)

import asyncio
import itertools
import enum
import copy
import os
import random
import abc

logger = structlog.get_logger()

T = TypeVar("T")

MAPSIZE = 15
WAIT_TIME = 5
ACTORNUM = 3
SENTINEL = object()

app = FastAPI()
command_queue = asyncio.Queue()


class MyBaseModel(BaseModel):
    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))


colors = {
    0: "\u001b[31m",
    1: "\u001b[32m",
    2: "\u001b[33m",
    3: "\u001b[34m",
    4: "\u001b[35m",
    5: "\u001b[36m",
    44: "\033[1m",
    99: "\x1b[0m",
}


base_place_matrix = [
    [[1, 4], [1, 4]],
    [[1, 4], [MAPSIZE - 5, MAPSIZE - 2]],
    [[MAPSIZE - 5, MAPSIZE - 2], [1, 4]],
    [[MAPSIZE - 5, MAPSIZE - 2], [MAPSIZE - 5, MAPSIZE - 2]],
]


class Directions(str, enum.Enum):
    left = "left"
    right = "right"
    down = "down"
    up = "up"


class Order(BaseModel):
    name: str = Field(decription="Name of the player to issue the order.")
    password: str = Field(
        decscription="The password for the player used during registering."
    )


class Coordinates(MyBaseModel):
    x: int = Field(
        description="X coodinate is decreased by the 'left' and increased by the 'right' direction.",
        ge=0,
        le=MAPSIZE - 1,
    )
    y: int = Field(
        description="Y coodinate is decreased by the 'down' and increased by the 'up' direction.",
        ge=0,
        le=MAPSIZE - 1,
    )


class AttackOrder(Order):
    actor: int = Field(
        title="Actor",
        description="The id of the actor, specific to the player.",
        ge=0,
        le=ACTORNUM - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description="The direction to attack from the position of the actor. Only actors with the attack property can attack.",
    )


class MoveOrder(Order):
    actor: int = Field(ge=0, le=ACTORNUM - 1)
    direction: Directions = Field(
        title="Direction",
        description=(
            "The direction to move to from the position of the actor. 'up' increases the y coordinate and 'right' increases the x coordinate. "
            "Moving over your own flag return it to the base."
        ),
    )


class GrabPutOrder(Order):
    actor: int = Field(
        title="Actor",
        description="The id of the actor, specific to the player.",
        ge=0,
        le=ACTORNUM - 1,
    )
    direction: Directions = Field(
        title="Direction",
        description=(
            "The direction to grap of put the flag from the position of the actor. "
            "If the actor has a flag it outs it, if it doesnt have a flag, it grabs it, even from another actor."
        ),
    )


class RegisterOrder(BaseModel):
    name: str
    password: str


class Player(BaseModel):
    name: str
    password: str
    number: int

    def __eq__(self, another):
        return hasattr(another, "name") and self.name == another.name

    def __hash__(self):
        return hash(self.name)


class States(str, enum.Enum):
    alive = "alive"
    stunned = "stunned"


class Actor(BaseModel, abc.ABC):
    name: str = "default"
    ident: int
    player: Player
    grab = 0.0
    attack = 0.0
    flag: int | None = None

    def __eq__(self, another):
        return (
            hasattr(another, "ident")
            and self.ident == another.ident
            and hasattr(another, "player")
            and self.player == another.player
        )

    def __hash__(self):
        return hash((self.ident, self.player))


class Generalist(Actor):
    name = "Generalist"
    grab = 1.0
    attack = 1.0


class Runner(Actor):
    name = "Runner"
    grab = 1.0


class Attacker(Actor):
    name = "Attacker"
    attack = 1.0


class InitialActorsList(BaseModel):
    actors: list[type[Actor]] = Field(min_items=ACTORNUM, max_items=ACTORNUM)


class StateResponse(BaseModel):
    actors_coordinates: dict[tuple[str, str, int], tuple[int, int]]
    test: dict[Actor, Coordinates]
    players: list[str]
    time_of_next_execution: float


class Board:
    def __init__(self, mapsize: int, walls=0) -> None:
        self.mapsize = mapsize
        self.walls = walls

        self.actors_coordinates: dict[Actor, Coordinates] = {}
        self.flags_coordinates: dict[int, Coordinates] = {}
        self.bases_coordinates: dict[int, Coordinates] = {}
        self.walls_coordinates: set[Coordinates] = set()

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
        base_coordinates = self.flags_coordinates[actor.player.number]
        possible_spawn_points = []
        for x in range(base_coordinates.x - 2, base_coordinates.x + 3):
            for y in range(base_coordinates.y - 2, base_coordinates.y + 3):
                possible_spawn_points.append(Coordinates(x=x, y=y))
        actor_positions = list(self.actors_coordinates.values())
        flag_positions = list(self.flags_coordinates.values())
        forbidden_positions = set(flag_positions + actor_positions)
        while True:
            target_coordinates = random.choice(possible_spawn_points)
            if target_coordinates not in forbidden_positions:
                actor.flag = None
                self.put_actor(actor, target_coordinates)
                logger.info(f"Actor {actor.player.name}-{actor.ident} respawned to coordinates {target_coordinates}")
                break

    def calc_target_coordinates(
        self, actor: Actor, direction: Directions
    ) -> Coordinates:
        coordinates = self.actors_coordinates[actor]
        new_coordinates = Coordinates(x=coordinates.x, y=coordinates.y)
        if direction == direction.right:
            new_coordinates.x = min(coordinates.x + 1, self.mapsize - 1)
        if direction == direction.left:
            new_coordinates.x = max(coordinates.x - 1, 0)
        if direction == direction.up:
            new_coordinates.y = min(coordinates.y + 1, self.mapsize - 1)
        if direction == direction.down:
            new_coordinates.y = max(coordinates.y - 1, 0)
        return new_coordinates

    def move(self, actor: Actor, direction: Directions) -> bool:
        new_coordinates = self.calc_target_coordinates(actor, direction)
        return self.put_actor(actor, new_coordinates)

    def put_actor(self, actor: Actor, new_coordinates: Coordinates) -> bool:
        coordinates = self.actors_coordinates[actor]

        # check if position is already inhabited by an actor or base or wall
        if (
            self.coordinates_actors.get(new_coordinates)
            or self.coordinates_bases.get(new_coordinates)
            or new_coordinates in self.walls_coordinates
        ):
            logger.info(f"Actor {actor.player.name}-{actor.ident} did not move. Target field is occupied.")
            return False

        # check if position has changed:
        if new_coordinates == coordinates:
            logger.info(f"Actor {actor.player.name}-{actor.ident} did not move. Board boundaries int he way.")
            return False

        self.actors_coordinates[actor] = new_coordinates
        # move flag if actor has it
        if actor.flag is not None:
            flag = actor.flag
            self.flags_coordinates[flag] = new_coordinates

        logger.info(f"Actor {actor.player.name}-{actor.ident} moved from {coordinates} to {new_coordinates}")
        return True

    def image(self) -> str:
        field = [["___" for _ in range(self.mapsize)] for _ in range(self.mapsize)]

        for i, base in enumerate(self.bases_coordinates.values()):
            field[base.y][base.x] = f" {colors[i]}\u25D9{colors[99]} "
        for actor, coordinates in self.actors_coordinates.items():
            char = actor.name[0].upper()
            color = colors[actor.player.number]
            field[coordinates.y][coordinates.x] = f" {color}{char}{colors[99]} "
        for flag, coordinates in self.flags_coordinates.items():
            color = colors[flag]
            before = field[coordinates.y][coordinates.x]
            field[coordinates.y][coordinates.x] = (
                before[:-2] + f" {color}\u25B2{colors[99]}"
            )
        for wall_coordinate in self.walls_coordinates:
            field[wall_coordinate.y][wall_coordinate.x] = "\u2588\u2588\u2588"
        for row in field:
            row.append("\n")
        # reverse so (0,0) is lower left not upper left
        field.reverse()
        joined = "".join(list(itertools.chain.from_iterable(field)))
        return joined

    def place_bases(self, players: int) -> None:
        available_places = list(range(len(base_place_matrix)))
        for i in range(players):
            place_chosen = random.choice(available_places)
            available_places.remove(place_chosen)
            x = random.randint(*base_place_matrix[place_chosen][0])
            y = random.randint(*base_place_matrix[place_chosen][1])
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
                x=random.randint(0, self.mapsize - 1),
                y=random.randint(0, self.mapsize - 1),
            )
            if coordinates not in forbidden_postions:
                self.walls_coordinates.add(coordinates)
                walls += 1


class Game:
    def __init__(
        self, board: Board, max_players: int, actors: InitialActorsList
    ) -> None:
        self.max_players = max_players
        self.actors = actors.actors
        self.board = board

        self.players: dict[str, Player] = {}
        self.players_actors: dict[tuple[Player, int], Actor] = {}
        self.scores: dict[int, int] = {}

        self.time_of_next_execution = 0.0
        self.tick = 0

    def initiate_game(self) -> None:
        self.set_scores()
        self.create_player_actors()
        self.place_actors_and_bases()

    def set_scores(self) -> None:
        for i in range(len(self.players)):
            self.scores[i] = 0

    def place_actors_and_bases(self) -> None:
        self.board.place_bases(len(self.players))
        for p, player in enumerate(self.players.values()):
            coordinates = self.board.bases_coordinates[p]
            actors = []
            for a in range(len(self.actors)):
                actors.append(self.players_actors[(player, a)])
                self.board.place_actors(actors, coordinates)
        self.board.place_walls()

    def create_player_actors(self) -> None:
        for player in self.players.values():
            for number, actor in enumerate(self.actors):
                self.players_actors[(player, number)] = actor(
                    ident=number, player=player
                )

    def actor_dict(self, value: T) -> dict[Actor, T]:
        value_dict = {}
        for actor in self.players_actors.values():
            value_dict[actor] = value
        return value_dict

    def validate_order(self, order: Order) -> bool:
        check = False
        if order.name in self.players.keys():
            check = self.players[order.name].password == order.password
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

        logger.info("Executing move orders.")
        self.execute_move_orders(move_orders)

        logger.info("Executing grab/put orders.")
        self.execute_grabput_orders(grabput_orders)

        logger.info("Executing attack orders.")
        self.execute_attack_orders(attack_orders)

    def execute_move_orders(self, move_orders: list[MoveOrder]) -> None:
        already_moved = self.actor_dict(False)
        for order in move_orders:
            actor = self.players_actors[(self.players[order.name], order.actor)]
            direction = order.direction
            if not already_moved[actor]:
                # if the actor can move
                already_moved[actor] = self.board.move(actor, direction)
                if already_moved[actor]:
                    self.check_flag_return_conditions(actor)

    def execute_attack_orders(self, attack_orders: list[AttackOrder]) -> None:
        already_attacked = self.actor_dict(False)
        for order in attack_orders:
            actor = self.players_actors[(self.players[order.name], order.actor)]

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
                    logger.info(f"Actor {actor.player.name}-{actor.ident} attacked and hit actor {target.player.name}-{target.ident}.")
                    self.board.respawn(target)
                    already_attacked[actor] = True

            else:
                logger.info(f"Actor {actor.player.name}-{actor.ident} did not attack. Actor can not attack or missed.")

    def execute_grabput_orders(self, grabput_orders: list[GrabPutOrder]):
        already_grabbed = self.actor_dict(False)
        for order in grabput_orders:
            actor = self.players_actors[(self.players[order.name], order.actor)]
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

            # if there is a target that already has a flag or can not carry it do nothing
            if target_actor is not None and (
                not target_actor.grab or target_actor.flag is not None
            ):
                logger.info(f"Actor {actor.player.name}-{actor.ident} can not hand the flag to actor {target_actor.player.name}-{target_actor.ident}.")
                already_grabbed = False
            # if the target coordinates are a wall
            elif target_coordinates in self.board.walls_coordinates:
                logger.info(f"Actor {actor.player.name}-{actor.ident} can not hand the flag to a wall.")
                already_grabbed = False

            # otherwise put the flag there
            else:
                self.board.flags_coordinates[flag] = target_coordinates
                actor.flag = None

                # and assign it to the target if there is one
                if target_actor is not None:
                    target_actor.flag = flag
                    logger.info(f"Actor {actor.player.name}-{actor.ident} handed the flag to actor {target_actor.player.name}-{target_actor.ident}.")
                    self.check_flag_return_conditions(actor)

                # the flag was put ont he field (maybe a base)
                else:
                    logger.info(f"Actor {actor.player.name}-{actor.ident} putthe flag to coordinates {target_coordinates}.")
                    self.check_score_conditions(flag, target_coordinates)

        # the actor does not have the flag
        else:
            # if the flag is at the target coordinates, grab it
            if flag := self.board.coordinates_flags.get(target_coordinates) is not None:
                self.board.flags_coordinates[flag] = self.board.actors_coordinates[
                    actor
                ]

                # and remove it from the target actor if there is one
                if target_actor is not None:
                    target_actor.flag = None

            # if there is no flag at the destionation, do nothing
            else:
                already_grabbed = False

        return already_grabbed

    def check_score_conditions(self, flag: int, coordinates: Coordinates) -> None:
        if coordinates in self.board.bases_coordinates.values():
            base = self.board.coordinates_bases[coordinates]
            # if flag is not standing on own base but another
            if base != flag:
                self.scores[base] += 1

    def check_flag_return_conditions(self, actor: Actor) -> None:
        coordinates = self.board.actors_coordinates[actor]
        if coordinates in self.board.flags_coordinates.values():
            flag = self.board.coordinates_flags[coordinates]
            # if flag is own flag, return it to base
            if flag == actor.player.number:
                self.board.flags_coordinates[flag] = self.board.bases_coordinates[flag]


@app.post("/command")
async def command(order: MoveOrder | AttackOrder | GrabPutOrder):
    command_queue.put_nowait(order)
    return {"message": "Command added."}


@app.post("/register")
async def register(order: RegisterOrder):
    if len(game.players) >= game.max_players:
        return {"message": "Maximum number of players reached"}
    game.players[order.name] = Player(
        name=order.name, password=order.password, number=len(game.players)
    )
    return {"message": "Successfully registered"}


@app.get("/state")
async def get_state():
    pass
    # TODO: think about serialization
    # return StateResponse(
    #     actors_coordinates=game.board.actors_coordinates,
    #     players=list(game.players.keys()),
    #     time_of_next_execution=game.time_of_next_execution,
    # )

game = Game(
    Board(mapsize=MAPSIZE, walls=10),
    max_players=3,
    actors=InitialActorsList(actors=[Runner, Attacker, Attacker]),
)

async def routine():
    waiting_seconds = 0
    max_wait = 10

    await logger.ainfo("Starting registration.")
    while (len(game.players) < game.max_players) and (waiting_seconds <= max_wait):
        waiting_seconds += 1
        await asyncio.sleep(1)

    await logger.ainfo("Initiating game.")
    game.initiate_game()

    while True:
        await command_queue.put(SENTINEL)
        commands = await get_all_queue_items(command_queue)

        os.system("cls" if os.name == "nt" else "clear")
        print(game.board.image())

        bind_contextvars(tick=game.tick)

        await logger.ainfo("Starting tick execution.")
        game.execute_gamestep(commands)

        await logger.ainfo("Waiting for game commands.")
        game.time_of_next_execution = asyncio.get_running_loop().time() + WAIT_TIME

        await asyncio.sleep(WAIT_TIME)


async def get_all_queue_items(queue):
    items = []
    item = await queue.get()
    while item is not SENTINEL:
        items.append(item)
        queue.task_done()
        item = await queue.get()
    queue.task_done()
    return items


async def ai_generator():
    await asyncio.sleep(1)
    await register(RegisterOrder(name="Schwubi", password="Dubi"))
    await register(RegisterOrder(name="Bubi", password="Wubi"))
    await register(RegisterOrder(name="Trubi", password="Fubi"))
    while True:
        await asyncio.sleep(10)
        await command_queue.put(
            MoveOrder(name="Schwubi", password="Dubi", actor=0, direction="up")
        )


@app.on_event("startup")
async def startup():
    asyncio.create_task(routine())
    asyncio.create_task(ai_generator())
