# Sample code from https://www.redblobgames.com/pathfinding/a-star/
# Copyright 2014 Red Blob Games <redblobgames@gmail.com>
#
# Feel free to use this code in your own projects, including commercial projects
# License: Apache v2.0 <http://www.apache.org/licenses/LICENSE-2.0.html>

from __future__ import annotations
import heapq

import numpy
import numpy.typing

from ascifight.board.data import Coordinates

# some of these types are deprecated: https://www.python.org/dev/peps/pep-0585/


class GridWithWeights:
    def __init__(
        self,
        width: int,
        height: int,
        blockers: list[Coordinates] | None = None,
        weights: numpy.typing.NDArray[numpy.float16] | None = None,
    ):
        self.width = width
        self.height = height
        self.blockers = blockers if blockers else []
        self.weights = (
            weights
            if weights is not None
            else numpy.ones((height, width), dtype=numpy.float16)
        )

    def passable(self, id: Coordinates) -> bool:
        return id not in self.blockers

    def in_bounds(self, coordinates) -> bool:
        x, y = coordinates
        return 0 <= x < self.width and 0 <= y < self.height

    def neighbors(self, id: Coordinates) -> filter[Coordinates]:
        (x, y) = id.x, id.y
        coords = filter(
            self.in_bounds, [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        )
        neighbors = [Coordinates(x=x, y=y) for x, y in coords]
        results = filter(self.passable, neighbors)
        return results

    def cost(self, coordinates: Coordinates) -> float:
        return self.weights[coordinates.y, coordinates.x]


class PriorityQueue:
    def __init__(self) -> None:
        self.elements: list[tuple[float, Coordinates]] = []

    def empty(self) -> bool:
        return not self.elements

    def put(self, item: Coordinates, priority: float) -> None:
        heapq.heappush(self.elements, (priority, item))

    def get(self) -> Coordinates:
        return heapq.heappop(self.elements)[1]


def dijkstra_search(
    graph: GridWithWeights, start: Coordinates, goal: Coordinates | None
) -> tuple[dict[Coordinates | None, Coordinates | None], dict[Coordinates, float]]:
    frontier = PriorityQueue()
    frontier.put(start, 0)
    came_from: dict[Coordinates | None, Coordinates | None] = {}
    cost_so_far: dict[Coordinates, float] = {}
    came_from[start] = None
    cost_so_far[start] = 0

    while not frontier.empty():
        current: Coordinates = frontier.get()

        if current == goal:
            break

        for next in graph.neighbors(current):
            new_cost = cost_so_far[current] + graph.cost(next)
            if next not in cost_so_far or new_cost < cost_so_far[next]:
                cost_so_far[next] = new_cost
                priority = new_cost
                frontier.put(next, priority)
                came_from[next] = current

    return came_from, cost_so_far


def reconstruct_path(
    came_from: dict[Coordinates | None, Coordinates | None],
    start: Coordinates,
    goal: Coordinates | None,
) -> list[Coordinates | None]:
    current = goal
    path = []
    if goal not in came_from:  # no path was found
        return []
    while current != start:
        path.append(current)
        current = came_from[current]
    path.append(start)  # optional
    path.reverse()  # optional
    return path


def heuristic(a: Coordinates, b: Coordinates) -> float:
    (x1, y1) = a.x, a.y
    (x2, y2) = b.x, b.y
    return abs(x1 - x2) + abs(y1 - y2)


def a_star_search(graph: GridWithWeights, start: Coordinates, goal: Coordinates):
    frontier = PriorityQueue()
    frontier.put(start, 0)
    came_from: dict[Coordinates, Coordinates | None] = {}
    cost_so_far: dict[Coordinates, float] = {}
    came_from[start] = None
    cost_so_far[start] = 0

    while not frontier.empty():
        current: Coordinates = frontier.get()

        if current == goal:
            break

        for next in graph.neighbors(current):
            new_cost = cost_so_far[current] + graph.cost(next)
            if next not in cost_so_far or new_cost < cost_so_far[next]:
                cost_so_far[next] = new_cost
                priority = new_cost + heuristic(next, goal)
                frontier.put(next, priority)
                came_from[next] = current

    return came_from, cost_so_far


def draw_tile(graph: GridWithWeights, id: Coordinates, style):
    r = " . "
    if "number" in style and id in style["number"]:
        r = " %-2d" % style["number"][id]
    if "point_to" in style and style["point_to"].get(id, None) is not None:
        (x1, y1) = id.x, id.y
        (x2, y2) = style["point_to"][id].x, style["point_to"][id].y
        if x2 == x1 + 1:
            r = " > "
        if x2 == x1 - 1:
            r = " < "
        if y2 == y1 + 1:
            r = " v "
        if y2 == y1 - 1:
            r = " ^ "
    if "path" in style and id in style["path"]:
        r = " @ "
    if "start" in style and id == style["start"]:
        r = " A "
    if "goal" in style and id == style["goal"]:
        r = " Z "
    if id in graph.blockers:
        r = "###"
    return r


def draw_grid(graph: GridWithWeights, **style):
    print("___" * graph.width)
    for y in reversed(range(graph.height)):
        for x in range(graph.width):
            print("%s" % draw_tile(graph, Coordinates(x=x, y=y), style), end="")
        print()
    print("~~~" * graph.width)


if __name__ == "__main__":
    diagram = GridWithWeights(
        10,
        10,
        blockers=[
            Coordinates(x=3, y=3),
            Coordinates(x=5, y=6),
            Coordinates(x=6, y=7),
            Coordinates(x=6, y=8),
        ],
    )
    start = Coordinates(x=2, y=2)
    goal: Coordinates | None = Coordinates(x=7, y=8)
    came_from, cost_so_far = dijkstra_search(diagram, start, goal)
    path = reconstruct_path(came_from, start=start, goal=goal)
    print(path)

    draw_grid(
        diagram,
        path=reconstruct_path(came_from, start=start, goal=goal),
        point_to=came_from,
        start=start,
        goal=goal,
    )

    came_from, cost_so_far = dijkstra_search(diagram, start, goal)
    draw_grid(
        diagram,
        path=reconstruct_path(came_from, start=start, goal=goal),
        number=cost_so_far,
        start=start,
        goal=goal,
    )
