import secrets
from typing import Annotated

from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends, HTTPException, status, Query, Path, Body

import ascifight.config as config
import ascifight.board.data as data
import ascifight.board.computations as computations

security = HTTPBasic()

tags_metadata = [
    {
        "name": "orders",
        "description": "Operations to give orders to your actors.",
    },
    {
        "name": "states",
        "description": "Operations to get state information about the game.",
    },
    {
        "name": "logistics",
        "description": "Operations to provide quality of life support.",
    },
    {
        "name": "computations",
        "description": "Computational functions that help to create 'AI' scripts.",
    },
    {
        "name": "web-page",
        "description": "Web-pages to display various information.",
    },
]

teams: dict[bytes, bytes] = {
    team["name"].encode("utf8"): team["password"].encode("utf8")
    for team in config.config["teams"]
}


def get_current_team(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    current_username_bytes = credentials.username.encode("utf8")

    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = b""
    if current_username_bytes in teams.keys():
        correct_password_bytes = teams[current_username_bytes]
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not is_correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


actor_annotation = Annotated[
    int,
    Path(
        title="Actor",
        description="The actor to act.",
        ge=0,
        le=len(config.config["game"]["actors"]) - 1,
    ),
]

direction_annotation = Annotated[
    computations.Directions,
    Query(
        title="Direction",
        description="The direction the actor should perform the action to.",
    ),
]

origin_annotation = Annotated[
    data.Coordinates,
    Body(
        title="Origin Coordinates",
        description="The coordinates of the origin field.",
    ),
]

target_annotation = Annotated[
    data.Coordinates,
    Body(
        title="Target Coordinates",
        description="The coordinates of the target field.",
    ),
]
