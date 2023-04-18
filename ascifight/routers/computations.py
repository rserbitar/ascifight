from fastapi import APIRouter

import ascifight.board.data as data
import ascifight.board.computations as computations

router = APIRouter(
    prefix="/computations",
    tags=["computations"],
)


@router.post("/direction")
async def get_direction(
    origin: data.Coordinates, target: data.Coordinates
) -> list[computations.Directions]:
    """Calculate the direction(s) to the target field from an origin field."""
    return computations.calc_target_coordinate_direction(origin, target)


@router.post("/distance")
async def get_distance(origin: data.Coordinates, target: data.Coordinates) -> int:
    """Calculate the distance in fields to the target field from an origin field."""
    return computations.distance(origin, target)
