import io

import pydantic
from PIL import Image, ImageDraw, ImageFont

import ascifight.config as config
import ascifight.board.data as data
import ascifight.board.actions as asci_actions
import ascifight.util as util


factor = int(config.config["image"]["size"] / config.config["game"]["map_size"])
map_size: int = config.config["game"]["map_size"]


class Icon(pydantic.BaseModel):
    name: str
    coordinates: data.Coordinates
    color: str


def draw_objects(
    image_draw,
    icon: Icon,
    fnt=ImageFont.truetype("DejaVuSansMono-Bold.ttf", int(factor / 2)),
):
    image_draw.text(
        (
            3 + icon.coordinates.x * factor,
            factor * map_size - int(factor * 3 / 4) - icon.coordinates.y * factor,
        ),
        icon.name,
        font=fnt,
        fill=util.color_rgb_mapping[icon.color],
    )


def draw_icons(
    image_draw,
    icon: Icon,
    fnt=ImageFont.truetype("DejaVuSansMono-Bold.ttf", int(factor)),
):
    image_draw.text(
        (
            3 + icon.coordinates.x * factor,
            factor * map_size - int(factor * 9 / 8) - icon.coordinates.y * factor,
        ),
        icon.name,
        font=fnt,
        fill=util.color_rgb_mapping[icon.color],
    )


def draw_annotations(
    image_draw,
    icon: Icon,
    fnt=ImageFont.truetype("DejaVuSansMono-Bold.ttf", int(factor / 2)),
):
    image_draw.text(
        (
            int(factor * 2 / 3) + icon.coordinates.x * factor,
            factor * map_size - int(factor * 3 / 4) - icon.coordinates.y * factor,
        ),
        icon.name,
        font=fnt,
        fill=util.color_rgb_mapping[icon.color],
    )


def draw_map(objects: list[Icon], annotations: list[Icon], icons: list[Icon]) -> bytes:
    # Create new black image of entire board
    w, h = config.config["game"]["map_size"], config.config["game"]["map_size"]
    img = Image.new("RGB", (w, h), (55, 55, 55))
    pixels = img.load()

    # Make pixels "black" where (row+col) is odd
    for i in range(w):
        for j in range(h):
            if (i + j) % 2:
                # ignore wrong PIL type here
                pixels[i, j] = (0, 0, 0)  # type: ignore

    img = img.resize((factor * w, factor * h), Image.NEAREST)

    # get a drawing context
    d = ImageDraw.Draw(img)

    # draw multiline text
    for icon in icons:
        draw_icons(d, icon)
    for object in objects:
        draw_objects(d, object)
    for annotation in annotations:
        draw_annotations(d, annotation)
    # img.save("test.png")
    buf = io.BytesIO()
    img.save(buf, format="png")
    return buf.getvalue()


def draw_game_map(
    board: data.BoardData, attacks: list[asci_actions.AttackAction]
) -> bytes:
    actors = [
        Icon(
            name=actor.__class__.__name__[0] + str(actor.ident),
            coordinates=coordinates,
            color=util.color_names[actor.team.number],
        )
        for actor, coordinates in board.actors_coordinates.items()
    ]
    deaths = [
        Icon(
            name=util.death_icon,
            coordinates=attack.destination,
            color=util.color_names[attack.target.team.number],
        )
        for attack in attacks
    ]
    bases = [
        Icon(
            name=util.base_icon,
            coordinates=coordinates,
            color=util.color_names[base.team.number],
        )
        for base, coordinates in board.bases_coordinates.items()
    ]
    walls = [
        Icon(
            name=util.wall_icon,
            coordinates=coordinates,
            color="white",
        )
        for coordinates in board.walls_coordinates
    ]
    flags = [
        Icon(
            name=util.flag_icon,
            coordinates=coordinates,
            color=util.color_names[flag.team.number],
        )
        for flag, coordinates in board.flags_coordinates.items()
    ]
    return draw_map(actors + bases + walls, flags, deaths)


if __name__ == "__main__":
    icons = [
        Icon(name="R1", coordinates=data.Coordinates(x=14, y=14), color="yellow"),
        Icon(name="R1", coordinates=data.Coordinates(x=0, y=4), color="blue"),
        Icon(name="R1", coordinates=data.Coordinates(x=2, y=14), color="green"),
        Icon(name="R1", coordinates=data.Coordinates(x=0, y=0), color="yellow"),
    ]

    annotations = [
        Icon(name="\u25B2", coordinates=data.Coordinates(x=2, y=4), color="yellow"),
    ]

    draw_map(icons, annotations, [])
