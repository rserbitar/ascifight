import pytest
import ascifight.board.computations as computations
import ascifight.board.data as data


@pytest.mark.parametrize(
    "coordinates, direction, map_size, result",
    [
        (
            data.Coordinates(x=10, y=10),
            computations.Directions.up,
            15,
            data.Coordinates(x=10, y=11),
        ),
        (
            data.Coordinates(x=4, y=0),
            computations.Directions.down,
            15,
            data.Coordinates(x=4, y=0),
        ),
        (
            data.Coordinates(x=10, y=10),
            computations.Directions.left,
            15,
            data.Coordinates(x=9, y=10),
        ),
        (
            data.Coordinates(x=14, y=10),
            computations.Directions.right,
            15,
            data.Coordinates(x=14, y=10),
        ),
    ],
)
def test_calc_target_coordinates(coordinates, direction, map_size, result):
    assert (
        computations.calc_target_coordinates(
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
            data.Coordinates(x=10, y=10),
            data.Coordinates(x=10, y=11),
            [computations.Directions.up],
        ),
        (
            data.Coordinates(x=4, y=1),
            data.Coordinates(x=4, y=0),
            [computations.Directions.down],
        ),
        (
            data.Coordinates(x=5, y=1),
            data.Coordinates(x=4, y=1),
            [computations.Directions.left],
        ),
        (
            data.Coordinates(x=4, y=1),
            data.Coordinates(x=5, y=1),
            [computations.Directions.right],
        ),
        (
            data.Coordinates(x=4, y=1),
            data.Coordinates(x=5, y=2),
            [computations.Directions.right, computations.Directions.up],
        ),
    ],
)
def test_calc_target_coordinate_direction(origin, target, result):
    assert set(
        computations.calc_target_coordinate_direction(origin=origin, target=target)
    ) == set(result)


@pytest.mark.parametrize(
    "origin, target, result",
    [
        (
            data.Coordinates(x=10, y=10),
            data.Coordinates(x=4, y=10),
            6,
        ),
        (
            data.Coordinates(x=4, y=4),
            data.Coordinates(x=4, y=0),
            4,
        ),
        (
            data.Coordinates(x=10, y=6),
            data.Coordinates(x=2, y=9),
            11,
        ),
    ],
)
def test_distance(origin, target, result):
    assert computations.distance(origin=origin, target=target) == result
