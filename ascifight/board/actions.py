from dataclasses import dataclass
from pydantic import ValidationError
import structlog
import enum

import random


import ascifight.board.data as data
import ascifight.config as config


class Directions(str, enum.Enum):
    left = "left"
    right = "right"
    down = "down"
    up = "up"


@dataclass
class Action:
    actor: data.Actor
    destination: data.Coordinates


@dataclass
class AttackAction(Action):
    target: data.Actor


@dataclass
class MoveAction(Action):
    origin: data.Coordinates


@dataclass
class GrabAction(Action):
    flag: data.Flag
    target: data.Actor | None = None


@dataclass
class PutAction(Action):
    flag: data.Flag
    target: data.Actor | None = None


@dataclass
class DestroyAction(Action):
    pass


@dataclass
class BuildAction(Action):
    pass


class BoardActions:
    def __init__(self, game_board_data: data.BoardData):
        self._logger = structlog.get_logger()
        self.board_data: data.BoardData = game_board_data

        self.config = config.config

    def move(
        self, actor: data.Actor, direction: Directions
    ) -> tuple[bool, data.Team | None, MoveAction | None]:
        team_that_captured = None
        new_coordinates = self._calc_target_coordinates(actor, direction)
        origin = actor.coordinates
        moved = self._try_put_actor(actor, new_coordinates)
        action: MoveAction | None = None
        if moved:
            team_that_captured = self._check_flag_return_conditions(actor)

            action = MoveAction(actor=actor, origin=origin, destination=new_coordinates)
        return moved, team_that_captured, action

    def attack(
        self, actor: data.Actor, direction: Directions
    ) -> tuple[bool, data.Team | None, AttackAction | None]:
        attacked = False
        action: AttackAction | None = None
        team_that_killed = None
        if not actor.attack:
            self._logger.warning(f"{actor} can not attack.")
        else:
            target_coordinates = self._calc_target_coordinates(actor, direction)
            target = self.board_data.coordinates_actors.get(target_coordinates)
            if target is None:
                self._logger.warning(
                    f"No target on target coordinates {target_coordinates}."
                )
            else:
                attack_successful = random.random() < actor.attack
                attacked = True
                if not attack_successful:
                    self._logger.info(f"{actor} attacked and missed {target}.")
                else:
                    self._logger.info(f"{actor} attacked and hit {target}.")
                    self._respawn(target)
                    team_that_killed = actor.team
                    action = AttackAction(
                        actor=actor, target=target, destination=target_coordinates
                    )
        return attacked, team_that_killed, action

    def build(
        self, actor: data.Actor, direction: Directions
    ) -> tuple[bool, BuildAction | None]:
        built = False
        action: BuildAction | None = None
        if not actor.build:
            self._logger.warning(f"{actor} can not build.")
        else:
            target_coordinates = self._calc_target_coordinates(actor, direction)
            illegal_target = (
                self.board_data.coordinates_actors.get(target_coordinates)
                or self.board_data.coordinates_bases.get(target_coordinates)
                or self.board_data.coordinates_flags.get(target_coordinates)
                or target_coordinates in self.board_data.walls_coordinates
            )
            if illegal_target:
                self._logger.warning("Target field is either not empty.")
            else:
                build_successful = random.random() < actor.build
                built = True
                if not build_successful:
                    self._logger.info("Building did not work.")
                else:
                    self._logger.info(
                        f"{actor} successfully built a wall at {target_coordinates}."
                    )
                    action = BuildAction(actor=actor, destination=target_coordinates)
                    self.board_data.walls_coordinates.add(target_coordinates)
        return built, action

    def destroy(
        self, actor: data.Actor, direction: Directions
    ) -> tuple[bool, DestroyAction | None]:
        destroyed = False
        action: DestroyAction | None = None
        if not actor.destroy:
            self._logger.warning(f"{actor} can not destroy.")
        else:
            target_coordinates = self._calc_target_coordinates(actor, direction)
            target = target_coordinates in self.board_data.walls_coordinates
            if not target:
                self._logger.warning("Target field does not contain a wall.")
            else:
                destroy_successful = random.random() < actor.destroy
                destroyed = True
                if not destroy_successful:
                    self._logger.info("Destruction did not work.")
                else:
                    self._logger.info(
                        f"{actor} successfully destroyed a wall at "
                        f" {target_coordinates}."
                    )
                    action = DestroyAction(actor=actor, destination=target_coordinates)
                    self.board_data.walls_coordinates.remove(target_coordinates)
        return destroyed, action

    def grabput_flag(
        self, actor: data.Actor, direction: Directions
    ) -> tuple[bool, None | data.Team, GrabAction | PutAction | None]:
        team_that_captured = None
        target_coordinates = self._calc_target_coordinates(actor, direction)
        action: GrabAction | PutAction | None = None
        grab_successful = random.random() < actor.grab
        target_actor = self.board_data.coordinates_actors.get(target_coordinates)
        already_grabbed = False
        flag: data.Flag | None

        if actor.flag is not None:
            flag = actor.flag

            if target_actor is not None:
                if not target_actor.grab:
                    self._logger.warning(
                        f"{actor} can not hand the flag to actor {target_actor}. "
                        " Can not have the flag."
                    )

                elif target_actor.flag is not None:
                    self._logger.warning(
                        f"{actor} can not hand the flag to actor {target_actor}. "
                        "Target already has a flag."
                    )

                else:
                    self.board_data.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    target_actor.flag = flag
                    already_grabbed = True
                    self._logger.info(f"{actor} handed the flag to {target_actor}.")
                    team_that_captured = self._check_flag_return_conditions(
                        target_actor
                    )
                    action = PutAction(
                        actor=actor,
                        target=target_actor,
                        destination=target_coordinates,
                        flag=flag,
                    )

            # no target actor, means empty field, wall or base (even a flag???)
            else:
                if target_coordinates in self.board_data.walls_coordinates:
                    self._logger.warning(f"{actor} can not hand the flag to a wall.")

                # the flag was put on the field (maybe a base)
                else:
                    self.board_data.flags_coordinates[flag] = target_coordinates
                    actor.flag = None
                    already_grabbed = True
                    self._logger.info(
                        f"{actor} put the flag to coordinates {target_coordinates}."
                    )
                    team_that_captured = self._check_capture_conditions(flag)
                    action = PutAction(
                        actor=actor, destination=target_coordinates, flag=flag
                    )
        # the actor does not have the flag
        else:
            flag = self.board_data.coordinates_flags.get(target_coordinates)
            if flag is None:
                self._logger.warning(f"No flag at coordinates {target_coordinates}.")
            else:
                if grab_successful:
                    self.board_data.flags_coordinates[flag] = actor.coordinates
                    actor.flag = flag
                    already_grabbed = True

                    # and remove it from the target actor if there is one
                    if target_actor is not None:
                        target_actor.flag = None
                        self._logger.info(
                            f"{actor} grabbed the flag of {flag.team} from "
                            "{target_actor}."
                        )
                        action = GrabAction(
                            actor=actor,
                            destination=target_coordinates,
                            target=target_actor,
                            flag=flag,
                        )
                    else:
                        self._logger.info(f"{actor} grabbed the flag of {flag.team}.")
                        action = GrabAction(
                            actor=actor,
                            destination=target_coordinates,
                            flag=flag,
                        )
                    team_that_captured = self._check_flag_return_conditions(actor=actor)
                else:
                    self._logger.info(f"{actor} grabbed and missed the flag.")

        return already_grabbed, team_that_captured, action

    def _calc_target_coordinates(
        self,
        actor: data.Actor,
        direction: Directions,
    ) -> data.Coordinates:
        coordinates = actor.coordinates
        new_coordinates = data.Coordinates(x=coordinates.x, y=coordinates.y)
        match direction:
            case direction.right:
                new_coordinates.x = min(coordinates.x + 1, self.board_data.map_size - 1)
            case direction.left:
                new_coordinates.x = max(coordinates.x - 1, 0)
            case direction.up:
                new_coordinates.y = min(coordinates.y + 1, self.board_data.map_size - 1)
            case direction.down:
                new_coordinates.y = max(coordinates.y - 1, 0)
        return new_coordinates

    def _check_capture_conditions(
        self, flag_to_capture: data.Flag | None = None
    ) -> data.Team | None:
        team_that_captured = None
        flags = (
            [flag_to_capture]
            if flag_to_capture
            else [flag for flag in self.board_data.flags_coordinates.keys()]
        )
        for flag_to_capture in flags:
            capture_flag_coordinates = self.board_data.flags_coordinates[
                flag_to_capture
            ]
            base_at_flag_coordinates = self.board_data.coordinates_bases.get(
                capture_flag_coordinates
            )
            # if the flag is an enemy flag and owner flag is also there
            if (
                # flag is on a base
                base_at_flag_coordinates is not None
                # flag is not on it own base
                and (flag_to_capture.team != base_at_flag_coordinates.team)
            ):
                scoring_team = base_at_flag_coordinates.team
                # own flag is at base or this is not required
                if not self.config["game"][
                    "home_flag_required"
                ] or self.board_data.flag_is_at_home(team=scoring_team):
                    self._logger.info(
                        f"{scoring_team} captured {flag_to_capture.team} flag!"
                    )
                    team_that_captured = scoring_team
                    # return the flag to the base it belongs to
                    self._return_flag_to_base(flag_to_capture)
                else:
                    self._logger.warning("Can not capture, flag not at home.")
        return team_that_captured

    def _respawn(self, actor: data.Actor) -> None:
        base_coordinates = self.board_data.bases_coordinates[data.Base(team=actor.team)]
        possible_spawn_points = []
        for x in range(base_coordinates.x - 2, base_coordinates.x + 3):
            for y in range(base_coordinates.y - 2, base_coordinates.y + 3):
                try:
                    possible_spawn_points.append(data.Coordinates(x=x, y=y))
                # ignore impossible positions
                except ValidationError:
                    pass
        actor_positions = list(self.board_data.actors_coordinates.values())
        flag_positions = list(self.board_data.flags_coordinates.values())
        base_positions = list(self.board_data.bases_coordinates.values())
        walls_positions = list(self.board_data.walls_coordinates)
        forbidden_positions = set(
            flag_positions + actor_positions + base_positions + walls_positions
        )
        self._place_actor_in_area(actor, possible_spawn_points, forbidden_positions)

    def _return_flag_to_base(self, flag: data.Flag) -> None:
        self.board_data.flags_coordinates[flag] = self.board_data.bases_coordinates[
            data.Base(team=flag.team)
        ]

    def _check_flag_return_conditions(self, actor: data.Actor) -> data.Team | None:
        team_that_captured = None
        coordinates = actor.coordinates
        if coordinates in self.board_data.flags_coordinates.values():
            flag = self.board_data.coordinates_flags[coordinates]
            # if flag is own flag, return it to base
            if flag.team == actor.team:
                self._return_flag_to_base(flag)
                team_that_captured = self._check_capture_conditions()
                if actor.flag:
                    actor.flag = None
        return team_that_captured

    def _place_actor_in_area(
        self,
        actor: data.Actor,
        possible_spawn_points: list[data.Coordinates],
        forbidden_positions: set[data.Coordinates],
    ) -> None:
        allowed_positions = set(possible_spawn_points) - set(forbidden_positions)
        target_coordinates = random.choice(list(allowed_positions))
        if actor.flag is not None:
            self._logger.info(f"{actor} dropped flag {actor.flag}.")
            actor.flag = None
        self.board_data.actors_coordinates[actor] = target_coordinates
        self._logger.info(f"{actor} respawned to coordinates {target_coordinates}.")

    def _get_area_positions(
        self, center: data.Coordinates, distance: int
    ) -> list[data.Coordinates]:
        positions: list[data.Coordinates] = []
        for x in range(center.x - distance, center.x + distance):
            for y in range(center.y - distance, center.y + distance):
                try:
                    positions.append(data.Coordinates(x=x, y=y))
                    # ignore forbidden space out of bounds
                except ValidationError:
                    pass
        return positions

    def _try_put_actor(
        self, actor: data.Actor, new_coordinates: data.Coordinates
    ) -> bool:
        coordinates = actor.coordinates
        moved = False

        if coordinates == new_coordinates:
            self._logger.warning(
                f"{actor} did not move. Target field is out of bounds."
            )
        elif self.board_data.coordinates_actors.get(new_coordinates) is not None:
            self._logger.warning(f"{actor} did not move. Target field is occupied.")
        elif self.board_data.coordinates_bases.get(new_coordinates) is not None:
            self._logger.warning(f"{actor} did not move. Target field is a base.")
        elif new_coordinates in self.board_data.walls_coordinates:
            self._logger.warning(f"{actor} did not move. Target field is a wall.")
        else:
            self.board_data.actors_coordinates[actor] = new_coordinates
            moved = True
            # move flag if actor has it
            if actor.flag is not None:
                flag = actor.flag
                self.board_data.flags_coordinates[flag] = new_coordinates

            self._logger.info(f"{actor} moved from {coordinates} to {new_coordinates}")

        return moved
