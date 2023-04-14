from pydantic import ValidationError
import toml
import structlog

import random
import itertools

import ascifight.board.data as data


class BoardSetup:
    def __init__(
        self,
        game_board_data: data.BoardData,
        teams: list[dict[str, str]],
        actors: list[str],
        map_size: int,
        walls: int,
    ):
        self._logger = structlog.get_logger()

        self.map_size = map_size
        self.board_data = game_board_data
        self.walls = walls

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

    def initialize_map(self):
        self.board_data.map_size = self.map_size
        self.board_data.names_teams = self.names_teams
        self.board_data.teams = self.teams
        self.board_data.actor_classes = self.actor_classes
        self._place_board_objects()

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

    def _place_bases_and_flags(self) -> None:
        available_places = list(range(len(self._base_place_matrix)))
        for team in self.teams:
            place_chosen = random.choice(available_places)
            available_places.remove(place_chosen)
            x = random.randint(*self._base_place_matrix[place_chosen][0])
            y = random.randint(*self._base_place_matrix[place_chosen][1])
            coordinates = data.Coordinates(x=x, y=y)
            self.board_data.bases_coordinates[data.Base(team=team)] = coordinates
            self.board_data.flags_coordinates[data.Flag(team=team)] = coordinates

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

    def _place_actors(self, actors: list[data.Actor], base: data.Coordinates) -> None:
        starting_places = self._get_area_positions(base, 2)
        starting_places.remove(base)
        random.shuffle(starting_places)
        starting_places = starting_places[: len(actors)]
        for actor, coordinates in zip(actors, starting_places):
            self.board_data.actors_coordinates[actor] = coordinates

    def _place_walls(self) -> None:
        forbidden_positions = set()
        for base_coordinates in self.board_data.bases_coordinates.values():
            forbidden_positions.update(self._get_area_positions(base_coordinates, 3))
        all_combinations = itertools.product(
            *[range(self.map_size), range(self.map_size)]
        )
        all_positions = {data.Coordinates(x=i[0], y=i[1]) for i in all_combinations}
        possible_coordinates = list(all_positions - forbidden_positions)
        random.shuffle(possible_coordinates)
        self.walls_coordinates = set(possible_coordinates[: self.walls])
