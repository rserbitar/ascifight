import pytest
import ascifight.board_computations as board_computations
import ascifight.board_data as board_data


@pytest.mark.parametrize(
    "coordinates, direction, map_size, result",
    [
        (
            board_data.Coordinates(x=10, y=10),
            board_computations.Directions.up,
            15,
            board_data.Coordinates(x=10, y=11),
        ),
        (
            board_data.Coordinates(x=4, y=0),
            board_computations.Directions.down,
            15,
            board_data.Coordinates(x=4, y=0),
        ),
        (
            board_data.Coordinates(x=10, y=10),
            board_computations.Directions.left,
            15,
            board_data.Coordinates(x=9, y=10),
        ),
        (
            board_data.Coordinates(x=14, y=10),
            board_computations.Directions.right,
            15,
            board_data.Coordinates(x=14, y=10),
        ),
    ],
)
def test_calc_target_coordinates(coordinates, direction, map_size, result):
    assert (
        board_computations.calc_target_coordinates(
            coordinates=coordinates,
            direction=direction,
            map_size=map_size,
        )
        == result
    )


@pytest.mark.parametrize(
    "origin, target, result",
    [
        (
            board_data.Coordinates(x=10, y=10),
            board_data.Coordinates(x=10, y=11),
            [board_computations.Directions.up],
        ),
        (
            board_data.Coordinates(x=4, y=1),
            board_data.Coordinates(x=4, y=0),
            [board_computations.Directions.down],
        ),
        (
            board_data.Coordinates(x=5, y=1),
            board_data.Coordinates(x=4, y=1),
            [board_computations.Directions.left],
        ),
        (
            board_data.Coordinates(x=4, y=1),
            board_data.Coordinates(x=5, y=1),
            [board_computations.Directions.right],
        ),
        (
            board_data.Coordinates(x=4, y=1),
            board_data.Coordinates(x=5, y=2),
            [board_computations.Directions.right, board_computations.Directions.up],
        ),
    ],
)
def test_calc_target_coordinate_direction(origin, target, result):
    assert set(
        board_computations.calc_target_coordinate_direction(
            origin=origin, target=target
        )
    ) == set(result)


@pytest.mark.parametrize(
    "origin, target, result",
    [
        (
            board_data.Coordinates(x=10, y=10),
            board_data.Coordinates(x=4, y=10),
            6,
        ),
        (
            board_data.Coordinates(x=4, y=4),
            board_data.Coordinates(x=4, y=0),
            4,
        ),
        (
            board_data.Coordinates(x=10, y=6),
            board_data.Coordinates(x=2, y=9),
            11,
        ),
    ],
)
def test_distance(origin, target, result):
    assert board_computations.distance(origin=origin, target=target) == result
