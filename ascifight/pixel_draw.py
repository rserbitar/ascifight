"""
Pixel based drawing routines
"""

import math
import typing
import annotated_types
from ascifight.board.data import Coordinates

width_type: typing.TypeAlias = typing.Annotated[float, annotated_types.Ge(1)]


def line(start: Coordinates, end: Coordinates, width: width_type = 1) -> set[Coordinates]:
    # There are some irregularities going on at certain parameter pairings, that I cannot track down. Maybe there
    # is something wrong with the algorithm? Algorithm is a simplified version of
    # http://kt8216.unixcab.org/murphy/index.html
    # Anyway, it works great for most combinations that you will encounter.
    width = 1 + (width - 1) / 2
    x0 = start.x
    x1 = end.x
    y0 = start.y
    y1 = end.y

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)

    if x0 < x1:
        x_step = 1
    elif x0 == x1:
        x_step = 0
    else:
        x_step = -1

    if y0 < y1:
        y_step = 1
    elif y0 == y1:
        y_step = 0
    else:
        y_step = -1

    if x_step == -1:
        if y_step == -1:
            perp_y_step = -1
            perp_x_step = 1
        elif y_step == 0:
            perp_y_step = -1
            perp_x_step = 0
        elif y_step == 1:
            perp_y_step = 1
            perp_x_step = 1
    elif x_step == 0:
        if y_step == -1:
            perp_y_step = 0
            perp_x_step = -1
        elif y_step == 0:
            perp_y_step = 0
            perp_x_step = 0
        elif y_step == 1:
            perp_y_step = 0
            perp_x_step = 1
    elif x_step == 1:
        if y_step == -1:
            perp_y_step = -1
            perp_x_step = -1
        elif y_step == 0:
            perp_y_step = -1
            perp_x_step = 0
        elif y_step == 1:
            perp_y_step = 1
            perp_x_step = 1

    if dx > dy:
        line = _x_line(x0, y0, dx, dy, x_step, y_step, width, perp_x_step, perp_y_step)
    else:
        line = _y_line(x0, y0, dx, dy, x_step, y_step, width, perp_x_step, perp_y_step)
    return line


#######################################################################################################################
#######################################################################################################################
#######################################################################################################################


def _x_perp_line(x0, y0, dx, dy, x_step, y_step, e_init, width, w_init):
    threshold = dx - 2 * dy
    e_diag = -2 * dx
    e_square = 2 * dy
    x_plus = x_minus = x0
    y_plus = y_minus = y0
    error = e_init
    tk = dx + dy - w_init
    line = set()
    while tk <= width:
        line.add(Coordinates(x=x_plus, y=y_plus))
        line.add(Coordinates(x=x_minus, y=y_minus))
        if error >= threshold:
            x_plus += x_step
            x_minus -= x_step
            error += e_diag
            tk += 2 * dy
        error += e_square
        y_plus += y_step
        y_minus -= y_step
        tk += 2 * dx
    return line


def _y_perp_line(x0, y0, dx, dy, x_step, y_step, e_init, width, w_init):
    threshold = dy - 2 * dx
    e_diag = -2 * dy
    e_square = 2 * dx
    x_plus = x_minus = x0
    y_plus = y_minus = y0
    error = -e_init
    tk = dx + dy - w_init
    line = set()
    while tk <= width:
        line.add(Coordinates(x=x_plus, y=y_plus))
        line.add(Coordinates(x=x_minus, y=y_minus))
        if error >= threshold:
            y_plus += y_step
            y_minus -= y_step
            error += e_diag
            tk += 2 * dy
        error += e_square
        x_plus += x_step
        x_minus -= x_step
        tk += 2 * dy
    return line


def _x_line(x0, y0, dx, dy, x_step, y_step, width, perp_x_step, perp_y_step):
    perp_error = 0
    error = 0
    x = x0
    y = y0
    threshold = dx - 2 * dy
    e_diag = -2 * dx
    e_square = 2 * dy
    length = dx + 1
    D = math.sqrt(dx * dx + dy * dy)
    width *= 2 * D
    line = set()
    for p in range(length):
        line.update(_x_perp_line(x, y, dx, dy, perp_x_step, perp_y_step, perp_error, width, error))
        if error > threshold:
            y += y_step
            error += e_diag
            if perp_error >= threshold:
                line.update(
                    _x_perp_line(x, y, dx, dy, perp_x_step, perp_y_step, perp_error + e_diag + e_square, width, error))
                perp_error += e_diag
            perp_error += e_square
        error += e_square
        x += x_step
    return line


def _y_line(x0, y0, dx, dy, x_step, y_step, width, perp_x_step, perp_y_step):
    perp_error = 0
    error = 0
    x = x0
    y = y0
    threshold = dy - 2 * dx
    e_diag = -2 * dy
    e_square = 2 * dx
    length = dy + 1
    D = math.sqrt(dx * dx + dy * dy)
    width *= 2 * D
    line = set()
    for p in range(length):
        line.update(_y_perp_line(x, y, dx, dy, perp_x_step, perp_y_step, perp_error, width, error))
        if error > threshold:
            x += x_step
            error += e_diag
            if perp_error >= threshold:
                line.update(
                    _y_perp_line(x, y, dx, dy, perp_x_step, perp_y_step, perp_error + e_diag + e_square, width, error))
                perp_error += e_diag
            perp_error += e_square
        error += e_square
        y += y_step

    return line
