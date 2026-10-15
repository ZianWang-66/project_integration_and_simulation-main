"""Regression tests for the IR-SIM safety layer and its import guard.

These tests do not need the simulator: they exercise the corridor perception,
the safety supervisor, the benchmark retry and the window/headless switch with
synthetic data.
"""

import subprocess

from shapely.geometry import Point, box

from test_irsim_with_agent import (FORWARD_SPEED, Perception, SafetySupervisor,
                                   TURN_RATE)

ROBOT_RADIUS = 0.2
STEP_TIME = 0.1


class _Robot:
    def __init__(self, radius=ROBOT_RADIUS):
        self.radius = radius


class _Obstacle:
    def __init__(self, geometry):
        self.geometry = geometry


class _Env:
    def __init__(self, geometries):
        self.obstacle_list = [_Obstacle(geometry) for geometry in geometries]
        self.robot = _Robot()
        self.robot_list = [self.robot]


def _perception(geometries):
    env = _Env(geometries)
    return Perception(env, env.robot, (0.0, 10.0, 0.0, 10.0))


def test_forward_is_refused_when_the_next_step_would_collide():
    # Box from x=1.6 onwards; with the robot radius and margin the centre has to
    # stay left of x=1.15.
    perception = _perception([box(1.6, 0.2, 2.6, 1.4)])
    supervisor = SafetySupervisor(perception, STEP_TIME)

    velocity, command = supervisor.command("FORWARD", 0.9, 0.6, 0.0, True)

    assert velocity[0] == 0.0, "the supervisor must not translate into an obstacle"
    assert abs(velocity[1]) == TURN_RATE, "it should rotate in place instead"
    assert command != "forward"
    assert supervisor.overrides == 1


def test_forward_is_allowed_when_the_step_is_clear():
    perception = _perception([box(3.0, 0.2, 4.0, 1.4)])
    supervisor = SafetySupervisor(perception, STEP_TIME)

    velocity, command = supervisor.command("FORWARD", 0.9, 0.6, 0.0, False)

    assert command == "forward"
    assert velocity[0] == FORWARD_SPEED
    assert velocity[1] == 0.0


def test_turns_never_translate():
    supervisor = SafetySupervisor(_perception([]), STEP_TIME)

    for action in ("LEFT", "RIGHT"):
        velocity, command = supervisor.command(action, 5.0, 5.0, 0.0, False)
        assert command == "turn"
        assert velocity[0] == 0.0
        assert abs(velocity[1]) == TURN_RATE


def test_forward_commands_never_step_into_an_obstacle():
    """Exhaustive sweep: every allowed forward step stays outside the obstacle."""
    obstacle = box(2.0, 2.0, 3.0, 3.0)
    dangerous = obstacle.buffer(ROBOT_RADIUS, quad_segs=64)
    perception = _perception([obstacle])
    supervisor = SafetySupervisor(perception, STEP_TIME)

    allowed = 0
    for x_index in range(80):
        x = 1.5 + 0.02 * x_index
        for y_index in range(41):
            y = 1.8 + 0.05 * y_index
            velocity, command = supervisor.command("FORWARD", x, y, 0.0, False)
            if command != "forward":
                continue
            allowed += 1
            next_step = Point(x + velocity[0] * STEP_TIME, y)
            assert not dangerous.contains(next_step), (x, y)

    assert allowed > 0, "the sweep should contain positions where forward is safe"


def test_walls_are_treated_as_obstacles():
    supervisor = SafetySupervisor(_perception([]), STEP_TIME)

    velocity, command = supervisor.command("FORWARD", 0.6, 5.0, 3.14159, True)

    assert velocity[0] == 0.0
    assert command != "forward"


def test_benchmark_retries_a_transient_subprocess_failure(tmp_path, monkeypatch):
    import benchmark_irsim

    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "irsim_worlds").mkdir()
    world = tmp_path / "irsim_worlds" / "world_test.yaml"
    world.write_text("world: {}\n", encoding="utf-8")

    calls = []

    def fake_run(world_file, headless=False):
        calls.append(world_file)
        if len(calls) == 1:
            return 1, "RuntimeError: internal error in regular expression engine", False
        (tmp_path / "artifacts" / "irsim_report.json").write_text(
            '{"reached_goal": true, "steps_taken": 3}', encoding="utf-8")
        return 0, "IR-SIM report: {'reached_goal': True, 'steps_taken': 3}", False

    monkeypatch.setattr(benchmark_irsim, "run_world_process", fake_run)
    report = benchmark_irsim.run_benchmark(str(world))

    assert len(calls) == 2
    assert report["attempts"] == 2
    assert report["reached_goal"] is True
    assert "attempt 1" in (tmp_path / "artifacts" / "world_test.log").read_text()


def test_benchmark_gives_up_after_repeated_failures(tmp_path, monkeypatch):
    import pytest
    import benchmark_irsim

    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "irsim_worlds").mkdir()
    world = tmp_path / "irsim_worlds" / "world_test.yaml"
    world.write_text("world: {}\n", encoding="utf-8")

    monkeypatch.setattr(benchmark_irsim, "run_world_process",
                        lambda world_file, headless=False: (1, "boom", False))
    with pytest.raises(RuntimeError, match="IR-SIM failed"):
        benchmark_irsim.run_benchmark(str(world), max_attempts=2)


def test_world_runs_with_its_window_unless_headless_was_asked(monkeypatch):
    import benchmark_irsim

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(benchmark_irsim.subprocess, "run", fake_run)

    benchmark_irsim.run_world_process("irsim_worlds/world_easy.yaml")
    benchmark_irsim.run_world_process("irsim_worlds/world_easy.yaml", headless=True)

    assert "--headless" not in commands[0], "the default run is the visible demo"
    assert "--quiet" not in commands[0]
    assert "--headless" in commands[1]


def test_matplotlib_guard_survives_a_regex_engine_failure(monkeypatch):
    import matplotlib_compat
    from matplotlib.artist import ArtistInspector

    class ExplodingRegex:
        def search(self, *args, **kwargs):
            raise RuntimeError("internal error in regular expression engine")

    class Widget:
        def set_thing(self, value):
            """Set the thing.

            ACCEPTS: one of {'a', 'b'}
            """

    matplotlib_compat.install()  # idempotent
    monkeypatch.setattr(ArtistInspector, "_get_valid_values_regex",
                        ExplodingRegex(), raising=False)

    assert ArtistInspector(Widget()).get_valid_values("thing") == "unknown"
