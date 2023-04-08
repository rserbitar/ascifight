from pydantic import BaseModel, ValidationError, Field
from typing import TypeVar
import structlog
from structlog.contextvars import bind_contextvars, unbind_contextvars
import random
import toml
import sys

import ascifight.board as board
import ascifight.util as util

with open("config.toml", mode="r") as fp:
    config = toml.load(fp)


T = TypeVar("T")


class Order(BaseModel):
    team: str = Field(description="Name of the team to issue the order.")
    password: str = Field(
        description="The password for the team used during registering."
    )

    def __str__(self):
        return f"Order by {self.team}"


class AttackOrder(Order):
    actor: int = Field(
        description="The id of the actor, specific to the team.",
        ge=0,
        le=len(config["game"]["actors"]) - 1,
    )
    direction: board.Directions = Field(
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
    direction: board.Directions = Field(
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
    direction: board.Directions = Field(
        title="Direction",
        description=(
            "The direction to grab of put the flag from the position of the actor. "
        ),
    )

    def __str__(self):
        return f"GrabPutOrder by Actor {self.team}-{self.actor} -> {self.direction}"


class Game:
    def __init__(
        self,
        game_board: board.Board = board.Board(),
        score_file=config["server"]["scores_file"],
        score_multiplier: int = config["game"]["score_multiplier"],
        max_ticks: int = config["game"]["max_ticks"],
        max_score: int = config["game"]["max_score"],
    ) -> None:
        self.logger = structlog.get_logger()
        self.score_file = score_file
        self.score_multiplier = score_multiplier

        self.board = game_board

        self.scores: dict[board.Team, int] = {}
        self.overall_score: dict[board.Team, int] = {}
        self.tick = 0
        self.max_ticks = max_ticks
        self.max_score = max_score

    def initiate_game(self) -> None:
        self._set_scores()
        self._read_scores()
        self.board.place_board_objects()

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
                f"{util.colors[team.number]}{team.name}: {score}{util.colors['revert']}"
                for team, score in self.scores.items()
            ]
        )
        overall_score = " - ".join(
            [
                f"{util.colors[team.number]}{team.name}: {score}{util.colors['revert']}"
                for team, score in self.overall_score.items()
            ]
        )
        return f"{util.colors['bold']}Overall Score{util.colors['revert']}: {overall_score} \n{util.colors['bold']}Current Score{util.colors['revert']}: {current_score}"

    def _set_scores(self) -> None:
        for team in self.board.names_teams.values():
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
                        self.overall_score[self.board.names_teams[team]] += score
                    # ignore score if team is not in current teams
                    except ValueError:
                        pass
        # if the file is not yet there assume default scores
        except FileNotFoundError:
            pass

    def _actor_dict(self, value: T) -> dict[board.Actor, T]:
        value_dict = {}
        for actor in self.board.teams_actors.values():
            value_dict[actor] = value
        return value_dict

    def _validate_order(self, order: Order) -> bool:
        check = False
        if order.team in self.board.names_teams.keys():
            check = self.board.names_teams[order.team].password == order.password
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
            actor = self.board.teams_actors[
                (self.board.names_teams[order.team], order.actor)
            ]
            direction = order.direction
            if already_moved[actor]:
                self.logger.warning(f"{actor} already moved this tick.")
            else:
                # if the actor can move
                already_moved[actor], team_that_scored = self.board.move(
                    actor, direction
                )
                if team_that_scored:
                    self.scores[team_that_scored] += 1

        unbind_contextvars("team")

    def _execute_attack_orders(self, attack_orders: list[AttackOrder]) -> None:
        already_attacked = self._actor_dict(False)
        for order in attack_orders:
            bind_contextvars(team=order.team)
            self.logger.info(f"Executing {order}")
            actor = self.board.teams_actors[
                (self.board.names_teams[order.team], order.actor)
            ]

            if already_attacked[actor]:
                self.logger.warning(f"{actor} already attacked this tick.")
            else:
                already_attacked[actor] = self.board.attack(actor, order.direction)

        unbind_contextvars("team")

    def _execute_grabput_orders(self, grabput_orders: list[GrabPutOrder]):
        already_grabbed = self._actor_dict(False)
        for order in grabput_orders:
            bind_contextvars(team=order.team)
            self.logger.info(f"Executing {order}")
            actor = self.board.teams_actors[
                (self.board.names_teams[order.team], order.actor)
            ]
            if not already_grabbed[actor]:
                already_grabbed[actor], team_that_scored = self.board.grabput_flag(
                    actor, order.direction
                )
                if team_that_scored:
                    self.scores[team_that_scored] += 1
            else:
                self.logger.warning(f"{actor} already grabbed this tick.")
        unbind_contextvars("team")

    def check_game_end(self):
        return (
            self.tick == self.max_ticks or max(self.scores.values()) == self.max_score
        )
