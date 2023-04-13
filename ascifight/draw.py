import io
import os

import pydantic
from PIL import Image, ImageDraw, ImageFont
import toml

import ascifight.board_data as board_data
import ascifight.util as util

absolute_path = os.path.dirname(__file__)
with open(f"{absolute_path}/config.toml", mode="r") as fp:
    config = toml.load(fp)


factor = int(config["image"]["size"] / config["game"]["map_size"])
map_size: int = config["game"]["map_size"]


class Icon(pydantic.BaseModel):
    name: str
    coordinates: board_data.Coordinates
    color: str


def draw_objects(
    image_draw,
    icon: Icon,
    fnt=ImageFont.truetype("FreeMonoBold.ttf", int(factor / 2)),
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


def draw_annotations(
    image_draw,
    icon: Icon,
    fnt=ImageFont.truetype("FreeMonoBold.ttf", int(factor / 2)),
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


def draw_map(
    icons: list[Icon],
    annotations: list[Icon],
) -> bytes:
    # Create new black image of entire board
    w, h = config["game"]["map_size"], config["game"]["map_size"]
    img = Image.new("RGB", (w, h), (55, 55, 55))
    pixels = img.load()

    # Make pixels "black" where (row+col) is odd
    for i in range(w):
        for j in range(h):
            if (i + j) % 2:
                # ignore wrong PIL type here
                pixels[i, j] = (0, 0, 0)  # type: ignore

    img = img.resize((factor * w, factor * h), Image.NEAREST)

    # get a font
    fnt = ImageFont.truetype("FreeMonoBold.ttf", int(factor / 2))

    # get a drawing context
    d = ImageDraw.Draw(img)

    # draw multiline text
    for icon in icons:
        draw_objects(d, icon, fnt)
    for annotation in annotations:
        draw_annotations(d, annotation, fnt)
    # img.save("test.png")
    buf = io.BytesIO()
    img.save(buf, format="png")
    return buf.getvalue()


if __name__ == "__main__":
    icons = [
        Icon(name="R1", coordinates=board_data.Coordinates(x=14, y=14), color="yellow"),
        Icon(name="R1", coordinates=board_data.Coordinates(x=0, y=4), color="blue"),
        Icon(name="R1", coordinates=board_data.Coordinates(x=2, y=14), color="green"),
        Icon(name="R1", coordinates=board_data.Coordinates(x=0, y=0), color="yellow"),
    ]

    annotations = [
        Icon(
            name="\u25B2", coordinates=board_data.Coordinates(x=2, y=4), color="yellow"
        ),
    ]

    draw_map(icons, annotations)
