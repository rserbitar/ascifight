import itertools
import math
import random
import typing

from pydantic import ValidationError
import structlog

import ascifight.board.data as data
import ascifight.pixel_draw as pixel_draw


MapStyle = typing.Literal["arabia", "blood_bath", "black_forest", "random"]


@typing.final
class BoardSetup:
    # Assumptions made in code below:
    #   1. Base angle is between -pi/2 and pi/2 (used when placing walls)
    #   2. Base angle is (close to) a multiple of pi/4 (used when placing bases)
    # Thus, only pi/4 and -pi/4 are valid
    base_angle = math.pi / 4

    def __init__(
        self,
        game_board_data: data.BoardData,
        teams: list[dict[str, str]],
        actors: list[str],
        map_size: int,
        walls: int | float,
        map_style: MapStyle,
    ):
        self._logger = structlog.get_logger()

        self.map_size = map_size
        self.board_data = game_board_data
        self.walls = walls
        self.num_players = len(teams)

        self.names_teams: dict[str, data.Team] = {
            team["name"]: data.Team(
                name=team["name"], password=team["password"], number=i
            )
            for i, team in enumerate(teams)
        }
        self.teams: list[data.Team] = list(self.board_data.names_teams.values())
        self.actor_classes: list[type[data.Actor]] = [
            self.board_data._get_actor(actor) for actor in actors
        ]

        if map_style == "random":
            map_style = random.choice(tuple(self.wall_placer.keys()))  # type: ignore
        self.map_style = map_style

    def initialize_map(self):
        self.board_data.map_size = self.map_size
        self.board_data.names_teams = self.names_teams
        self.board_data.teams = self.teams
        self.board_data.actor_classes = self.actor_classes
        self._place_board_objects()

    def _place_board_objects(self) -> None:
        self._place_bases_and_flags()
        for team in self.teams:
            for number, actor_class in enumerate(self.actor_classes):
                self.board_data.teams_actors[(team, number)] = actor_class(
                    ident=number, team=team, board=self.board_data
                )
            coordinates = self.board_data.bases_coordinates[data.Base(team=team)]
            actors = [
                self.board_data.teams_actors[(team, a)]
                for a in range(len(self.actor_classes))
            ]
            self._place_actors(actors, coordinates)
        self._place_walls()

    def _maximum_distance(self) -> int:
        return int((1.4142 if self.num_players in (2, 4) else 1) * self.map_size / 2)

    def _place_bases_and_flags(self) -> None:
        half_size = self.map_size / 2
        minimum_distance = int(half_size / 2)  # At least half map radius from center
        if self.map_style == "black_forest":
            # move bases further out, to avoid wasted space
            minimum_distance = int(half_size * 0.75)
        maximum_distance = (
            self._maximum_distance() - 2
        )  # At least two distance from border

        # With the settings above, this is equivalent to a minimum map size of 6 (or 9
        # for black_forest), though much larger values (20+) are recommended in any
        # case.
        assert maximum_distance > minimum_distance

        random_distance = random.randint(minimum_distance, maximum_distance)
        angle_step = 2 * math.pi / self.num_players
        for i, team in enumerate(self.teams):
            pos_x = int(
                math.sin(self.base_angle + i * angle_step) * random_distance + half_size
            )
            pos_y = int(
                math.cos(self.base_angle + i * angle_step) * random_distance + half_size
            )
            starting_pos = data.Coordinates(x=pos_x, y=pos_y)
            self.board_data.bases_coordinates[data.Base(team=team)] = starting_pos
            self.board_data.flags_coordinates[
                data.Flag(team=team, board=self.board_data)
            ] = starting_pos

    def _get_area_positions(
        self, center: data.Coordinates, distance: int
    ) -> list[data.Coordinates]:
        positions: list[data.Coordinates] = []
        for x in range(center.x - distance, center.x + distance + 1):
            for y in range(center.y - distance, center.y + distance + 1):
                try:
                    positions.append(data.Coordinates(x=x, y=y))
                    # ignore forbidden space out of bounds
                except ValidationError:
                    pass
        return positions

    def _place_actors(self, actors: list[data.Actor], base: data.Coordinates) -> None:
        starting_places = self._get_area_positions(base, 2)
        starting_places.remove(base)
        random.shuffle(starting_places)
        starting_places = starting_places[: len(actors)]
        for actor, coordinates in zip(actors, starting_places):
            self.board_data.actors_coordinates[actor] = coordinates

    def _place_walls(self):
        self.wall_placer[self.map_style](self)

    def _place_walls_arabia(self) -> None:
        """
        Random (but mirrored for each team) distribution of walls. self.walls governs
        the target number (integer) or density (if float between 0 and 1) of wall tiles.

        Be careful with high wall densities, as there are no guaranteed paths between
        bases.
        """
        min_angle = self.base_angle - (math.pi / self.num_players)
        angle_range = 2 * math.pi / self.num_players
        half_size = self.map_size / 2

        if 0 < self.walls < 1:
            num_walls = int(self.walls * self.map_size * self.map_size)
        else:
            num_walls = typing.cast(int, self.walls)

        forbidden_positions = set()
        for base_coordinates in self.board_data.bases_coordinates.values():
            forbidden_positions.update(self._get_area_positions(base_coordinates, 2))

        angle_step = 2 * math.pi / self.num_players
        num_walls_placed = 0
        misses = 0
        maximum_distance = self._maximum_distance()
        while num_walls_placed < num_walls:
            # The method of generating random angles and distances works much better
            # than any method involving sampling
            # points from a set of allowed points, because now we do not have to bother
            # with the pesky math along the
            # middle axes of the board, which is prone to rounding- and
            # off-by-one-errors.
            # Unfortunately, nothing really works perfectly for 3 or >= 5 players. That
            # is just maths, because you
            # cannot map these symmetries onto discrete squares without any bias.
            angle = random.random() * angle_range + min_angle
            # The inverse CDF of a linear PDF is the square root. Knowing that, we do a
            # Smirnov transform
            random_distance = math.sqrt(random.random()) * maximum_distance
            for i in range(self.num_players):
                pos_x = int(
                    math.sin(angle + i * angle_step) * random_distance + half_size
                )
                pos_y = int(
                    math.cos(angle + i * angle_step) * random_distance + half_size
                )
                if 0 <= pos_x < self.map_size and 0 <= pos_y < self.map_size:
                    coordinate = data.Coordinates(x=pos_x, y=pos_y)
                    if (
                        coordinate not in self.board_data.walls_coordinates
                        and coordinate not in forbidden_positions
                    ):
                        self.board_data.walls_coordinates.add(coordinate)
                        num_walls_placed += 1
                    else:
                        # We do not count corner misses, those are an unfortunate
                        # byproduct but do not hurt
                        misses += 1

            if misses > 100 and num_walls_placed / misses < 0.1:
                break

        if num_walls and self.num_players not in (2, 4):
            # Fill outer circle with walls to avoid bias provided by the map corners
            # This too, cannot work perfectly, because there will be inherent bias in
            # odd symmetries due to the square grid.
            maximum_distance_squared = maximum_distance * maximum_distance
            for x in range(self.map_size):
                for y in range(self.map_size):
                    distance_squared = (x - half_size) ** 2 + (y - half_size) ** 2
                    if distance_squared > maximum_distance_squared:
                        coordinate = data.Coordinates(x=x, y=y)
                        if coordinate not in forbidden_positions:
                            self.board_data.walls_coordinates.add(coordinate)

    def _place_walls_blood_bath(self) -> None:
        """
        Place solid walls between the bases with a shared path through the center.
        walls parameter governs the length of the walls (Integer: Absolute length,
        but be careful about that! Float: Percentage of the map size).
        """
        if not self.walls:
            return

        min_angle = self.base_angle - (math.pi / self.num_players)
        angle_step = 2 * math.pi / self.num_players
        half_size = self.map_size / 2

        if 0 < self.walls < 1:
            wall_length = self.walls * half_size
        else:
            wall_length = self.walls

        min_x = int((1 * half_size) - wall_length)
        max_x = int(1.5 * half_size)

        for x in range(min_x, max_x):
            for i in range(self.num_players):
                pos_x = round(x * math.cos(min_angle + i * angle_step) + half_size)
                pos_y = round(x * math.sin(min_angle + i * angle_step) + half_size)
                if 0 <= pos_x < self.map_size and 0 <= pos_y < self.map_size:
                    coordinate = data.Coordinates(x=pos_x, y=pos_y)
                    self.board_data.walls_coordinates.add(coordinate)

    def _place_walls_black_forest(self) -> None:
        """
        Map filled with walls, with a few paths between bases, one from each base to
        each other base.

        The walls parameter influences the width of the paths (higher number of walls
        -> narrower paths) but only slightly. The path width is always between 2 and 5.
        """
        forbidden_positions = set()
        for base_coordinates in self.board_data.bases_coordinates.values():
            forbidden_positions.update(self._get_area_positions(base_coordinates, 2))

        default_width = 5
        if 0 < self.walls < 1:
            width = default_width * (1 - self.walls)
        else:
            width = default_width - self.walls
        width = max(2, width)

        for base_coordinate1, base_coordinate2 in itertools.combinations(
            self.board_data.bases_coordinates.values(), 2
        ):
            path = pixel_draw.line(base_coordinate1, base_coordinate2, width=width)
            forbidden_positions.update(path)

        for x in range(self.map_size):
            for y in range(self.map_size):
                coordinate = data.Coordinates(x=x, y=y)
                if coordinate not in forbidden_positions:
                    self.board_data.walls_coordinates.add(coordinate)

    wall_placer = {
        "arabia": _place_walls_arabia,
        "blood_bath": _place_walls_blood_bath,
        "black_forest": _place_walls_black_forest,
    }
