"""Grid-based A* router for KiCad schematic wire segments."""

from __future__ import annotations

import heapq
from dataclasses import dataclass

Point = tuple[float, float]
Segment = tuple[float, float, float, float]


@dataclass(frozen=True)
class RouterBBox:
    """Axis-aligned obstacle bounds in millimetres."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains(self, point: Point) -> bool:
        x_mm, y_mm = point
        return self.x_min <= x_mm <= self.x_max and self.y_min <= y_mm <= self.y_max


class SchematicRouter:
    """A* schematic router with Manhattan movement and bend penalties."""

    def __init__(
        self,
        grid_mm: float = 2.54,
        obstacles: list[RouterBBox] | None = None,
        max_steps: int = 200,
    ) -> None:
        self.grid_mm = grid_mm
        self.obstacles = list(obstacles or [])
        self.max_steps = max_steps

    def _grid(self, point: Point) -> tuple[int, int]:
        return (round(point[0] / self.grid_mm), round(point[1] / self.grid_mm))

    def _point(self, node: tuple[int, int]) -> Point:
        return (node[0] * self.grid_mm, node[1] * self.grid_mm)

    def _blocked(self, node: tuple[int, int], start: tuple[int, int], end: tuple[int, int]) -> bool:
        if node in {start, end}:
            return False
        point = self._point(node)
        return any(obstacle.contains(point) for obstacle in self.obstacles)

    @staticmethod
    def _heuristic(node: tuple[int, int], end: tuple[int, int]) -> float:
        return abs(node[0] - end[0]) + abs(node[1] - end[1])

    def route(self, start: Point, end: Point, max_bends: int = 4) -> list[Segment] | None:
        """Return routed Manhattan segments, or None if no bounded route is found."""
        start_node = self._grid(start)
        end_node = self._grid(end)
        queue: list[tuple[float, int, tuple[int, int], tuple[int, int] | None, int]] = []
        heapq.heappush(queue, (0.0, 0, start_node, None, 0))
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_node: None}
        best_cost: dict[tuple[int, int], float] = {start_node: 0.0}
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        explored = 0

        while queue and explored < self.max_steps:
            _, bends, current, previous_dir, _tie = heapq.heappop(queue)
            explored += 1
            if current == end_node:
                return self._segments_from_path(self._reconstruct(came_from, current))

            for direction in directions:
                nxt = (current[0] + direction[0], current[1] + direction[1])
                if self._blocked(nxt, start_node, end_node):
                    continue
                next_bends = bends + (1 if previous_dir and previous_dir != direction else 0)
                if next_bends > max_bends:
                    continue
                move_cost = 1.0 + (3.0 if previous_dir and previous_dir != direction else 0.0)
                new_cost = best_cost[current] + move_cost
                if new_cost >= best_cost.get(nxt, float("inf")):
                    continue
                came_from[nxt] = current
                best_cost[nxt] = new_cost
                priority = new_cost + self._heuristic(nxt, end_node)
                heapq.heappush(queue, (priority, next_bends, nxt, direction, explored))
        return None

    @staticmethod
    def _reconstruct(
        came_from: dict[tuple[int, int], tuple[int, int] | None],
        current: tuple[int, int],
    ) -> list[tuple[int, int]]:
        path = [current]
        previous = came_from[current]
        while previous is not None:
            current = previous
            path.append(current)
            previous = came_from[current]
        path.reverse()
        return path

    def _segments_from_path(self, path: list[tuple[int, int]]) -> list[Segment]:
        if len(path) < 2:
            return []
        points = [self._point(node) for node in path]
        segments: list[Segment] = []
        start = points[0]
        previous = points[0]
        direction = (
            int(points[1][0] - points[0][0]),
            int(points[1][1] - points[0][1]),
        )
        for point in points[1:]:
            next_direction = (
                int(point[0] - previous[0]),
                int(point[1] - previous[1]),
            )
            if next_direction != direction:
                segments.append((start[0], start[1], previous[0], previous[1]))
                start = previous
                direction = next_direction
            previous = point
        segments.append((start[0], start[1], previous[0], previous[1]))
        return [segment for segment in segments if segment[:2] != segment[2:]]
