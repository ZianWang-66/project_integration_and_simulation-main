"""IR-SIM runner for the generated navigation logic.

Usage
-----
    python test_irsim_with_agent.py irsim_worlds/world_easy.yaml
    python test_irsim_with_agent.py irsim_worlds/world_easy.yaml --headless --quiet

The artifact under test is the Developer Agent's ``decide_next_move(state)``.
This runner owns everything around it:

1. Perception.  The six boolean flags are measured against the real obstacle
   polygons (buffered by the robot radius plus a safety margin) and against the
   arena boundary.  "front_blocked" therefore means "moving a full step that way
   would eat into the safety margin", not "an obstacle centre happens to be in
   roughly that direction".
2. Safety supervision.  LEFT and RIGHT are executed as rotations in place,
   which cannot translate the robot into anything because the robot is a disc;
   FORWARD is only issued when a corridor check proves that the next step stays
   clear of every obstacle and of the walls.  Once the robot starts dodging, it
   keeps rotating the same way until the front corridor is clear again, which
   removes the left/right oscillation that used to walk the robot into box
   corners.
3. Reporting.  ``artifacts/irsim_report.json`` plus the printed report line,
   both consumed by ``benchmark_irsim.py``.

Without ``--headless`` the run draws into a window while it drives and holds the
final frame for ``env.end()``; it never blocks in a GUI main loop, so the script
always returns.
"""

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np

# The guard must be installed before matplotlib/irsim are imported.
import matplotlib_compat  # noqa: F401
import irsim
from shapely.geometry import LineString, Point, box
from shapely.ops import nearest_points

from generated.navigation_logic import decide_next_move

MAX_STEPS = 300
EFFICIENT_STEP_LIMIT = 200

# Motion primitives.  The worlds allow [-1, 1] m/s and [-1, 1] rad/s, so these
# stay inside the limits: 0.10 m per step forward, 0.10 rad per step turning.
FORWARD_SPEED = 1.0
TURN_RATE = 1.0

# Clearance kept by the supervisor.
SAFETY_MARGIN = 0.25
LOOK_AHEAD = 1.0           # horizon of the front/left/right flags
RELEASE_LOOK_AHEAD = 1.3   # longer horizon before a dodge counts as finished
GOAL_HALF_ANGLE = 0.4      # goal counts as "ahead" within this heading error

# Deadlock recovery: rotate decisively instead of grinding against a corner.
STALL_WINDOW = 40
STALL_DISTANCE = 0.25
ESCAPE_STEPS = 12


def classify_efficiency(reached_goal_status, steps_taken):
    """
    Classify a run based on goal completion and step count.

    The benchmark keeps 300 as the hard runtime limit, but treats
    anything above 200 steps as successful-but-inefficient.
    """
    if not reached_goal_status:
        return "failed"
    if steps_taken <= EFFICIENT_STEP_LIMIT:
        return "efficient"
    return "acceptable_but_inefficient"


def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def angle_diff(a, b):
    return normalize_angle(a - b)


def reached_goal(robot, goal, tolerance=0.4):
    x = robot.state[0, 0]
    y = robot.state[1, 0]
    return math.hypot(x - goal[0], y - goal[1]) <= tolerance


def world_bounds(world_file, env):
    """Arena limits as (x_min, x_max, y_min, y_max)."""
    try:
        import yaml

        data = yaml.safe_load(Path(world_file).read_text(encoding="utf-8")) or {}
        world = data.get("world", {}) or {}
        width = float(world.get("width", 10.0))
        height = float(world.get("height", 10.0))
        offset = list(world.get("offset", [0.0, 0.0]))
        x_min, y_min = float(offset[0]), float(offset[1])
        return x_min, x_min + width, y_min, y_min + height
    except Exception:  # pragma: no cover - fall back to the loaded world object
        return (float(env._world.x_range[0]), float(env._world.x_range[1]),
                float(env._world.y_range[0]), float(env._world.y_range[1]))


class Perception:
    """Corridor clearance checks against inflated obstacles and walls."""

    def __init__(self, env, robot, bounds):
        self.radius = float(robot.radius)
        self.inflate = self.radius + SAFETY_MARGIN
        self.obstacles = []
        for obj in env.obstacle_list:
            geometry = getattr(obj, "geometry", None)
            if geometry is None or geometry.is_empty:
                continue
            # Buffering a polygon by the robot radius is the exact Minkowski sum
            # for a disc-shaped robot; the safety margin rides on top of it.
            self.obstacles.append(geometry.buffer(self.inflate, quad_segs=64))
        x_min, x_max, y_min, y_max = bounds
        # Free-space region for the robot centre.
        self.arena = box(x_min + self.inflate, y_min + self.inflate,
                         x_max - self.inflate, y_max - self.inflate)

    def blocked(self, x, y, heading, length):
        """True when the corridor of *length* along *heading* is not free."""
        segment = LineString([(x, y),
                              (x + length * math.cos(heading),
                               y + length * math.sin(heading))])
        if not self.arena.covers(segment):
            return True
        return any(segment.intersects(obstacle) for obstacle in self.obstacles)

    def clearance(self, x, y):
        """Distance still available before touching anything (robot surface)."""
        point = Point(x, y)
        distances = [point.distance(obstacle) for obstacle in self.obstacles]
        distances.append(point.distance(self.arena.boundary))
        return min(distances) + SAFETY_MARGIN

    def threat_bearing(self, x, y):
        """Absolute bearing of the closest obstacle or wall, or None if empty."""
        point = Point(x, y)
        closest = None
        for geometry in list(self.obstacles) + [self.arena.boundary]:
            distance = point.distance(geometry)
            if closest is None or distance < closest[0]:
                target = nearest_points(point, geometry)[1]
                closest = (distance, math.atan2(target.y - y, target.x - x))
        return None if closest is None else closest[1]


class SafetySupervisor:
    """Turns the policy's action into a collision-free velocity command."""

    def __init__(self, perception, step_time):
        self.perception = perception
        self.step_length = FORWARD_SPEED * step_time
        self.evade_direction = 0
        self.escape_direction = 0
        self.escape_steps_remaining = 0
        self.last_escape_direction = 0
        self.overrides = 0
        self.dodges = 0
        self.escapes = 0
        self.stalled = False
        self._window = []

    # -- safety queries -------------------------------------------------
    def forward_step_clear(self, x, y, heading):
        """The robot may translate only if the next step is provably clear."""
        return not self.perception.blocked(x, y, heading,
                                           self.step_length + SAFETY_MARGIN)

    def avoid_direction(self, x, y, heading):
        """Rotate away from the closest obstacle or wall (-1 right, +1 left)."""
        bearing = self.perception.threat_bearing(x, y)
        if bearing is None:
            return 1
        offset = angle_diff(bearing, heading)
        if offset > 0.05:      # threat on the left
            return -1
        if offset < -0.05:     # threat on the right
            return 1
        return 1               # straight ahead: pick a side deterministically

    # -- stall recovery -------------------------------------------------
    def note_position(self, x, y):
        self._window.append((x, y))
        if len(self._window) > STALL_WINDOW:
            self._window.pop(0)
        if len(self._window) < STALL_WINDOW:
            self.stalled = False
            return
        dx = self._window[-1][0] - self._window[0][0]
        dy = self._window[-1][1] - self._window[0][1]
        self.stalled = math.hypot(dx, dy) < STALL_DISTANCE

    def _start_escape(self, x, y, heading):
        direction = self.evade_direction or self.avoid_direction(x, y, heading)
        if self.escapes and direction == self.last_escape_direction:
            direction = -direction  # same way stalled twice: try the other side
        self.escape_direction = direction
        self.last_escape_direction = direction
        self.escape_steps_remaining = ESCAPE_STEPS - 1
        self.escapes += 1
        self._window.clear()

    # -- command --------------------------------------------------------
    @staticmethod
    def _drive():
        return np.array([FORWARD_SPEED, 0.0], dtype=float)

    @staticmethod
    def _turn(direction):
        return np.array([0.0, TURN_RATE * direction], dtype=float)

    def command(self, action, x, y, heading, front_blocked):
        # Commit to one dodge direction while the front is blocked: flipping
        # sides next to an obstacle is what used to steer the robot into it.
        if front_blocked:
            if not self.evade_direction:
                self.evade_direction = self.avoid_direction(x, y, heading)
        elif not self.perception.blocked(x, y, heading, RELEASE_LOOK_AHEAD):
            self.evade_direction = 0

        if self.escape_steps_remaining > 0:
            self.escape_steps_remaining -= 1
            return self._turn(self.escape_direction), "escape"

        if self.stalled:
            self._start_escape(x, y, heading)
            return self._turn(self.escape_direction), "escape"

        if action == "FORWARD":
            if self.forward_step_clear(x, y, heading):
                return self._drive(), "forward"
            self.overrides += 1
            self.dodges += 1
            return self._turn(self.evade_direction
                              or self.avoid_direction(x, y, heading)), "dodge"

        if action in ("LEFT", "RIGHT"):
            direction = 1 if action == "LEFT" else -1
            if front_blocked and self.evade_direction:
                direction = self.evade_direction
            return self._turn(direction), "turn"

        # STOP: hold when standing still is safe, otherwise keep rotating in
        # place (never translating) to re-plan instead of stalling forever.
        if self.forward_step_clear(x, y, heading):
            return np.zeros(2, dtype=float), "stop"
        self.overrides += 1
        return self._turn(self.evade_direction
                          or self.avoid_direction(x, y, heading)), "replan"


def build_state(perception, x, y, heading, goal):
    """The six flags handed to ``decide_next_move``."""
    state = {
        "front_blocked": perception.blocked(x, y, heading, LOOK_AHEAD),
        "left_blocked": perception.blocked(x, y, heading + math.pi / 2, LOOK_AHEAD),
        "right_blocked": perception.blocked(x, y, heading - math.pi / 2, LOOK_AHEAD),
    }
    goal_angle = math.atan2(goal[1] - y, goal[0] - x)
    offset = angle_diff(goal_angle, heading)
    state["goal_ahead"] = abs(offset) <= GOAL_HALF_ANGLE
    state["goal_on_left"] = offset > GOAL_HALF_ANGLE
    state["goal_on_right"] = offset < -GOAL_HALF_ANGLE
    return state


def simulate(env, world_file, quiet=False):
    """Run one world and return the report dict."""
    robot = env.robot_list[0]
    goal = [float(robot.goal[0, 0]), float(robot.goal[1, 0])]
    perception = Perception(env, robot, world_bounds(world_file, env))
    supervisor = SafetySupervisor(perception, float(env.world_param.step_time))
    if not quiet:
        print("LOADED GOAL FROM WORLD:", goal)

    history = []
    collisions = 0
    min_clearance = float("inf")
    path_length = 0.0
    termination = "max_steps"
    previous = None

    for step in range(MAX_STEPS):
        x = float(robot.state[0, 0])
        y = float(robot.state[1, 0])
        heading = float(robot.state[2, 0])
        if previous is not None:
            path_length += math.hypot(x - previous[0], y - previous[1])
        previous = (x, y)
        min_clearance = min(min_clearance, perception.clearance(x, y))
        supervisor.note_position(x, y)

        state = build_state(perception, x, y, heading, goal)
        action = decide_next_move(state.copy())
        velocity, command = supervisor.command(action, x, y, heading,
                                               state["front_blocked"])

        history.append({
            "step": step + 1,
            "robot_state": [x, y, heading],
            "perception_state": state,
            "action": action,
            "command": command,
            "velocity": [float(velocity[0]), float(velocity[1])],
        })
        if not quiet:
            print(f"Step {step + 1:3d} | pose=({x:5.2f},{y:5.2f},{heading:5.2f}) | "
                  f"blocked F/L/R={int(state['front_blocked'])}"
                  f"{int(state['left_blocked'])}{int(state['right_blocked'])} | "
                  f"action={str(action):7s} -> {command}")

        env.step(velocity, action_id=0)
        if env.display:
            env.render()

        if robot.collision:
            collisions += 1
            termination = "collision"
            break
        if reached_goal(robot, goal):
            termination = "goal_reached"
            break
        if env.done():
            termination = "robot_stopped"
            break

    reached_goal_status = reached_goal(robot, goal)
    steps_taken = len(history)
    efficiency_status = classify_efficiency(reached_goal_status, steps_taken)
    report = {
        "world": world_file,
        "reached_goal": bool(reached_goal_status),
        "collision_or_done": bool(env.done() or collisions),
        "collisions": int(collisions),
        "safety_overrides": int(supervisor.overrides),
        "escape_maneuvers": int(supervisor.escapes),
        "min_clearance": (round(min_clearance, 3)
                          if min_clearance < float("inf") else None),
        "path_length": round(path_length, 3),
        "steps_taken": steps_taken,
        "max_steps_allowed": MAX_STEPS,
        "efficient_step_limit": EFFICIENT_STEP_LIMIT,
        "efficiency_status": efficiency_status,
        "efficiency_passed": efficiency_status == "efficient",
        "termination": termination,
        "final_pose": [float(robot.state[0, 0]), float(robot.state[1, 0]),
                       float(robot.state[2, 0])],
        "history_length": len(history),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Run one IR-SIM world.")
    parser.add_argument("world", nargs="?", default="irsim_worlds/world_easy.yaml",
                        help="world YAML to run")
    parser.add_argument("--headless", action="store_true",
                        help="no figure or window (used by the benchmark)")
    parser.add_argument("--quiet", action="store_true", help="no per-step lines")
    args = parser.parse_args()

    headless = args.headless or os.environ.get("IRSIM_HEADLESS") == "1"
    env = irsim.make(args.world, display=not headless, headless=headless)
    try:
        report = simulate(env, args.world, quiet=args.quiet or headless)
    finally:
        env.end()

    print("\nIR-SIM report:")
    print(report)
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/irsim_report.json").write_text(json.dumps(report, indent=2),
                                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
