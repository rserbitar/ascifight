import math
import typing

from pydantic import ValidationError
import structlog

import random

import ascifight.board.data as data


MapStyle = typing.Literal['arabia', 'black_forest', 'blood_bath', 'random']


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
            map_style: MapStyle
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

        if map_style == 'random':
            map_style = random.choice(tuple(self.wall_placer.keys()))
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
                    ident=number, team=team
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
        maximum_distance = self._maximum_distance() - 2  # At least two distance from border

        # With 2 minimum distance to border and half radius to center, this is equivalent to a minimum map size of 11
        assert maximum_distance > minimum_distance

        random_distance = random.randint(minimum_distance, maximum_distance)
        angle_step = 2 * math.pi / self.num_players
        for i, team in enumerate(self.teams):
            pos_x = int(math.sin(self.base_angle + i * angle_step) * random_distance + half_size)
            pos_y = int(math.cos(self.base_angle + i * angle_step) * random_distance + half_size)
            starting_pos = data.Coordinates(x=pos_x, y=pos_y)
            self.board_data.bases_coordinates[data.Base(team=team)] = starting_pos
            self.board_data.flags_coordinates[data.Flag(team=team)] = starting_pos

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
        min_angle = self.base_angle - (math.pi / self.num_players)
        angle_range = (2 * math.pi / self.num_players)
        half_size = self.map_size / 2

        if 0 < self.walls < 1:
            num_walls = int(self.walls * self.map_size * self.map_size)
        else:
            num_walls = self.walls

        forbidden_positions = set()
        for base_coordinates in self.board_data.bases_coordinates.values():
            forbidden_positions.update(self._get_area_positions(base_coordinates, 2))

        angle_step = 2 * math.pi / self.num_players
        num_walls_placed = 0
        misses = 0
        maximum_distance = self._maximum_distance()
        while num_walls_placed < num_walls:
            # The method of generating random angles and distances works much better than any method involving sampling
            # points from a set of allowed points, because now we do not have to bother with the pesky math along the
            # middle axes of the board, which is prone to rounding- and off-by-one-errors.
            # Unfortunately, nothing really works perfectly for 3 or >= 5 players. That is just maths, because you
            # cannot map these symmetries onto discrete squares without any bias.
            angle = random.random() * angle_range + min_angle
            # The inverse CDF of a linear PDF is the square root. Knowing that, we do a Smirnov transform
            random_distance = math.sqrt(random.random()) * maximum_distance
            for i in range(self.num_players):
                pos_x = int(math.sin(angle + i * angle_step) * random_distance + half_size)
                pos_y = int(math.cos(angle + i * angle_step) * random_distance + half_size)
                if 0 <= pos_x < self.map_size and 0 <= pos_y < self.map_size:
                    coordinate = data.Coordinates(x=pos_x, y=pos_y)
                    if coordinate not in self.board_data.walls_coordinates and coordinate not in forbidden_positions:
                        self.board_data.walls_coordinates.add(coordinate)
                        num_walls_placed += 1
                    else:
                        # We do not count corner misses, those are an unfortunate byproduct but do not hurt
                        misses += 1

            if misses > 100 and num_walls_placed / misses < 0.1:
                break

        if num_walls and self.num_players not in (2, 4):
            # Fill outer circle with walls to avoid bias provided by the map corners
            # This too, cannot work perfectly, because there will be inherent bias in odd symmetries due to the square
            # grid.
            maximum_distance_squared = maximum_distance * maximum_distance
            for x in range(self.map_size):
                for y in range(self.map_size):
                    distance_squared = (x-half_size) ** 2 + (y-half_size) **2
                    if distance_squared > maximum_distance_squared:
                        coordinate = data.Coordinates(x=x, y=y)
                        if coordinate not in forbidden_positions:
                            self.board_data.walls_coordinates.add(coordinate)

    wall_placer = {'arabia': _place_walls_arabia}
