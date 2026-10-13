"""Independent module-51 specification examples; does not access/run Spore.

Own seconds and metres are explicit. No original ANIM time conversion is used.
Existing evidence is checked read-only. Run with bundled Python and -B.
"""
from dataclasses import dataclass, field
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Diagnostic(ValueError):
    pass


def number(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise Diagnostic("NonFiniteClockInput")
    try:
        return value if isinstance(value, F) else F(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise Diagnostic("InvalidClockNumber") from exc


def nonnegative(value):
    x = number(value)
    if x < 0:
        raise Diagnostic("NegativeClockInput")
    return x


def crossed(previous, current, period, markers, cap=256):
    """Ordered loop occurrences in (previous,current]; marker zero is start separately.

    Marker identity is ordinal, not its display name. Preflight capacity before
    enumerating potentially huge jumps. Fractions make boundary policy testable.
    """
    p, c, length = nonnegative(previous), nonnegative(current), number(period)
    if length <= 0:
        raise Diagnostic("NonPositiveLoopPeriod")
    if c < p:
        raise Diagnostic("BackwardCursor")
    if not isinstance(cap, int) or cap < 0:
        raise Diagnostic("InvalidOccurrenceCapacity")
    windows = []
    for ordinal, raw in enumerate(markers):
        m = nonnegative(raw)
        if m >= length:
            raise Diagnostic("LoopMarkerOutsideHalfOpenPeriod")
        first = max(0, (p - m) // length + 1)
        last = (c - m) // length
        windows.append((ordinal, m, first, last))
    count = sum(max(0, last - first + 1) for _, _, first, last in windows)
    if count > cap:
        raise Diagnostic("OccurrenceCapacityExceeded")
    return sorted((cycle * length + m, cycle, ordinal)
                  for ordinal, m, first, last in windows
                  for cycle in range(first, last + 1))


@dataclass
class Action:
    duration: F = F(1)
    # (own action seconds, gameplay effect-slot identity)
    markers: tuple = ((F(35, 100), "hit"), (F(65, 100), "recover"))
    elapsed: F = F(0)
    rate: F = F(1)
    paused: bool = False
    state: str = "Running"
    generation: int = 7
    body_revision: int = 3
    epoch: int = 1
    last_tick: int = -1
    committed: set = field(default_factory=set)
    emitted: list = field(default_factory=list)

    def __post_init__(self):
        self.duration = number(self.duration)
        if self.duration <= 0:
            raise Diagnostic("NonPositiveActionDuration")
        self.markers = tuple((nonnegative(t), slot) for t, slot in self.markers)
        if any(t > self.duration for t, _ in self.markers):
            raise Diagnostic("ActionMarkerOutsideDuration")
        if list(self.markers) != sorted(self.markers):
            raise Diagnostic("UnsortedActionMarkers")

    def ticket(self):
        return self.generation, self.body_revision, self.epoch

    def commit(self, ticket, slot):
        if ticket != self.ticket():
            raise Diagnostic("StaleActionTicket")
        if self.state != "Running":
            raise Diagnostic("InactiveAction")
        if slot not in self.committed:
            self.committed.add(slot)
            self.emitted.append(slot)
            return True
        return False

    def start(self):
        for time, slot in self.markers:
            if time == 0:
                self.commit(self.ticket(), slot)

    def step(self, dt, tick):
        delta, rate = nonnegative(dt), nonnegative(self.rate)
        if tick <= self.last_tick:
            raise Diagnostic("DuplicateOrOldSimulationTick")
        if self.state != "Running":
            raise Diagnostic("InactiveAction")
        old = self.elapsed
        new = old if self.paused else min(self.duration, old + delta * rate)
        pending = [slot for t, slot in self.markers if old < t <= new]
        self.last_tick, self.elapsed = tick, new
        for slot in pending:
            self.commit(self.ticket(), slot)
        if new == self.duration:
            self.state = "Completed"
        return new - old

    def cancel(self):
        self.epoch += 1
        if self.state == "Running":
            self.state = "Cancelled"


@dataclass
class VisualLoop:
    length: F = F(1)
    markers: tuple = (F(0), F(1, 4))
    cursor: F = F(0)
    epoch: int = 11
    seen: set = field(default_factory=set)

    def start(self):
        for i, m in enumerate(self.markers):
            if number(m) == 0:
                self.seen.add((self.epoch, 0, i))

    def advance(self, dt, rate=1, pause=False, cap=256):
        delta, speed = nonnegative(dt), nonnegative(rate)
        new = self.cursor if pause else self.cursor + delta * speed
        events = crossed(self.cursor, new, self.length, self.markers, cap)
        keys = [(self.epoch, cycle, ordinal) for _, cycle, ordinal in events]
        fresh = [k for k in keys if k not in self.seen]
        self.seen.update(fresh)
        self.cursor = new
        return fresh


OFFSETS = (F(0), F(1, 2), F(1, 3), F(5, 6), F(2, 3), F(1, 6))


@dataclass
class Gait:
    cycles: F = F(0)
    mode: str = "Moving"
    settle_elapsed: F = F(0)
    settle_duration: F = F(15, 100)
    # Own convention: these offsets begin stance; no recovered limb mapping.
    def advance_distance(self, distance, stride=1):
        d, s = nonnegative(distance), number(stride)
        if s <= 0:
            raise Diagnostic("NonPositiveStride")
        if self.mode != "Moving":
            raise Diagnostic("GaitNotMoving")
        self.cycles += d / s

    def phases(self):
        return tuple((self.cycles + x) % 1 for x in OFFSETS)

    def contacts(self):
        return tuple(True for _ in OFFSETS) if self.mode == "Stopped" else tuple(p < F(1, 2) for p in self.phases())

    def emergency_stop(self):
        self.mode = "Settling"
        self.settle_elapsed = F(0)

    def settle(self, dt):
        delta = nonnegative(dt)
        if self.mode != "Settling":
            raise Diagnostic("NotSettling")
        self.settle_elapsed = min(self.settle_duration, self.settle_elapsed + delta)
        if self.settle_elapsed == self.settle_duration:
            self.mode = "Stopped"
        return self.settle_elapsed / self.settle_duration


def arm_plan(path_length, interval, speed_limit):
    length, duration, limit = nonnegative(path_length), number(interval), number(speed_limit)
    if duration <= 0 or limit <= 0:
        raise Diagnostic("InvalidArmTimingBudget")
    # Own min-jerk path derivative has peak factor 1.875. Average is insufficient.
    peak = F(15, 8) * length / duration
    if peak > limit:
        raise Diagnostic("ArmPeakVelocityBudgetExceeded")
    return {"duration": duration, "peak_m_per_second": peak}


class ClockTests(unittest.TestCase):
    def test_01_frame_jump_crosses_both_action_markers(self):
        a = Action(); a.step(.8, 1)
        self.assertEqual(a.emitted, ["hit", "recover"])
    def test_02_action_frame_partition_has_same_commits(self):
        a, b = Action(), Action(); a.step(.8, 1)
        for i in range(8): b.step(.1, i)
        self.assertEqual(a.emitted, b.emitted); self.assertEqual(a.elapsed, b.elapsed)
    def test_03_exact_marker_boundary_once(self):
        a = Action(); a.step(.35, 1); a.step(0, 2); a.step(.01, 3)
        self.assertEqual(a.emitted, ["hit"])
    def test_04_zero_marker_requires_explicit_start_and_is_deduplicated(self):
        a = Action(markers=((F(0), "start"),)); a.start(); a.start(); a.step(.2, 1)
        self.assertEqual(a.emitted, ["start"])
    def test_05_action_pause_freezes_authority_then_resumes(self):
        a = Action(); a.step(.3, 1); a.paused = True; a.step(.7, 2)
        self.assertEqual(a.elapsed, F(3, 10)); self.assertEqual(a.emitted, [])
        a.paused = False; a.step(.05, 3); self.assertEqual(a.emitted, ["hit"])
    def test_06_action_double_rate_moves_commit_world_time(self):
        a = Action(); a.step(.4, 1); a.rate = 2; a.step(.125, 2)
        self.assertEqual(a.elapsed, F(65, 100)); self.assertEqual(a.emitted, ["hit", "recover"])
    def test_07_visual_rate_and_pause_do_not_move_action_clock(self):
        a, v = Action(), VisualLoop(); v.advance(.4, 3); v.advance(.9, pause=True)
        self.assertEqual(a.elapsed, 0); self.assertEqual(a.emitted, [])
    def test_08_loop_large_jump_preserves_cycles_and_zero_boundary(self):
        v = VisualLoop(); v.start(); found = v.advance(F(13, 4))
        self.assertEqual(len(found), 7)
        self.assertEqual(found, [(11, 0, 1), (11, 1, 0), (11, 1, 1), (11, 2, 0), (11, 2, 1), (11, 3, 0), (11, 3, 1)])
    def test_09_wrapped_equal_phase_is_not_no_motion(self):
        v = VisualLoop(markers=(F(1, 4),)); found = v.advance(2)
        self.assertEqual(v.cursor % 1, 0); self.assertEqual(len(found), 2)
    def test_10_loop_frame_partition_has_same_occurrences(self):
        a, b = VisualLoop(), VisualLoop(); a.start(); b.start(); a.advance(3.25)
        for _ in range(13): b.advance(.25)
        self.assertEqual(a.seen, b.seen)
    def test_11_distinct_equal_time_markers_retain_identity(self):
        v = VisualLoop(markers=(F(1, 4), F(1, 4)))
        self.assertEqual(v.advance(.25), [(11, 0, 0), (11, 0, 1)])
    def test_12_crossfade_two_visuals_cannot_duplicate_gameplay_slot(self):
        a = Action(); ticket = a.ticket()
        self.assertTrue(a.commit(ticket, "hit")); self.assertFalse(a.commit(ticket, "hit"))
        self.assertEqual(a.emitted, ["hit"])
    def test_13_cancel_keeps_committed_effect_rejects_old_ticket(self):
        a = Action(); ticket = a.ticket(); a.step(.4, 1); a.cancel()
        self.assertEqual(a.committed, {"hit"})
        with self.assertRaisesRegex(Diagnostic, "StaleActionTicket"): a.commit(ticket, "recover")
    def test_14_cancel_before_hit_cannot_emit_late(self):
        a = Action(); a.cancel()
        with self.assertRaisesRegex(Diagnostic, "InactiveAction"): a.step(.8, 1)
        self.assertEqual(a.committed, set())
    def test_15_duplicate_tick_diagnostic_does_not_advance(self):
        a = Action(); a.step(.2, 1)
        with self.assertRaisesRegex(Diagnostic, "DuplicateOrOld"): a.step(.6, 1)
        self.assertEqual(a.elapsed, F(1, 5)); self.assertEqual(a.committed, set())
    def test_16_negative_and_nonfinite_inputs_diagnostic(self):
        a = Action()
        for dt in (-1, math.inf, math.nan):
            with self.assertRaises(Diagnostic): a.step(dt, 1)
        a.rate = -1
        with self.assertRaisesRegex(Diagnostic, "NegativeClockInput"): a.step(.1, 1)
        self.assertEqual(a.elapsed, 0); self.assertEqual(a.last_tick, -1)
    def test_17_capacity_error_is_atomic_even_for_billion_cycles(self):
        v = VisualLoop(); before = v.cursor, set(v.seen)
        with self.assertRaisesRegex(Diagnostic, "OccurrenceCapacity"): v.advance(10**9)
        self.assertEqual((v.cursor, v.seen), before)
    def test_18_invalid_loop_period_or_endpoint_is_diagnostic(self):
        with self.assertRaisesRegex(Diagnostic, "NonPositive"): crossed(0, 1, 0, [0])
        with self.assertRaisesRegex(Diagnostic, "OutsideHalfOpen"): crossed(0, 1, 1, [1])
        with self.assertRaisesRegex(Diagnostic, "BackwardCursor"): crossed(2, 1, 1, [.2])
    def test_19_end_marker_fires_before_completion_and_clamps(self):
        a = Action(markers=((F(1), "end"),)); a.step(4, 1)
        self.assertEqual((a.elapsed, a.state, a.emitted), (F(1), "Completed", ["end"]))
    def test_20_body_revision_and_generation_invalidate_callback(self):
        a = Action(); ticket = a.ticket(); a.body_revision += 1
        with self.assertRaisesRegex(Diagnostic, "StaleActionTicket"): a.commit(ticket, "hit")
        a = Action(); ticket = a.ticket(); a.generation += 1
        with self.assertRaisesRegex(Diagnostic, "StaleActionTicket"): a.commit(ticket, "hit")


class GaitAndGeometryTests(unittest.TestCase):
    def test_21_six_leg_phase_at_numerical_example(self):
        g = Gait(); g.advance_distance(F(4, 5))
        self.assertEqual(g.phases(), (F(4, 5), F(3, 10), F(2, 15), F(19, 30), F(7, 15), F(29, 30)))
        self.assertEqual(g.contacts(), (False, True, True, False, True, False))
    def test_22_paused_arm_does_not_reset_moving_gait(self):
        g, a = Gait(), Action(); a.paused = True; a.step(.2, 1); g.advance_distance(.4)
        self.assertEqual(a.elapsed, 0); self.assertEqual(g.cycles, F(2, 5))
    def test_23_actual_displacement_zero_means_no_stride_even_if_desired_speed_high(self):
        g = Gait(); g.advance_distance(0)
        self.assertEqual(g.cycles, 0)
    def test_24_emergency_stop_freezes_cycle_then_lands_three_feet(self):
        g = Gait(); g.advance_distance(F(9, 5)); g.emergency_stop()
        old = g.phases(); self.assertEqual(sum(g.contacts()), 3)
        g.settle(.1); self.assertEqual(g.phases(), old); self.assertEqual(sum(g.contacts()), 3)
        g.settle(.05); self.assertEqual(g.phases(), old); self.assertEqual(sum(g.contacts()), 6)
    def test_25_stop_does_not_accept_movement_or_silent_phase_reset(self):
        g = Gait(); g.advance_distance(.8); g.emergency_stop()
        with self.assertRaisesRegex(Diagnostic, "GaitNotMoving"): g.advance_distance(.2)
        self.assertEqual(g.cycles, F(4, 5))
    def test_26_invalid_stride_and_negative_distance(self):
        g = Gait()
        for distance, stride in [(1, 0), (-.1, 1), (1, -1)]:
            with self.assertRaises(Diagnostic): g.advance_distance(distance, stride)
        self.assertEqual(g.cycles, 0)
    def test_27_long_arm_changes_trajectory_keeps_locked_time(self):
        short, long = arm_plan(.4, .35, 5), arm_plan(.8, .35, 5)
        self.assertEqual(short["duration"], long["duration"])
        self.assertEqual(long["peak_m_per_second"], F(30, 7))
    def test_28_peak_velocity_rejects_path_which_average_would_accept(self):
        self.assertLess(F(11, 10) / F(35, 100), 5)
        with self.assertRaisesRegex(Diagnostic, "PeakVelocityBudget"): arm_plan(1.1, .35, 5)


class ReusedEvidenceTests(unittest.TestCase):
    def test_29_reused_evidence_hashes_unchanged(self):
        m = json.loads((ROOT / "evidence/public-animation-clock-contracts.json").read_text(encoding="utf-8"))
        for item in m["reused_local_inputs"]:
            p = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), item["sha256"], str(p))
    def test_30_eight_headers_preserve_unknown_units(self):
        d = json.loads((ROOT / "evidence/local-selected-action-events.json").read_text(encoding="utf-8"))
        self.assertEqual(len(d["records"]), 8)
        for r in d["records"]:
            h = r["anim_events"]["header"]
            self.assertEqual(h["frameLengthWordRaw"], "0x3d088889")
            self.assertIn(h["length_raw"], [51, 50, 46, 39])
    def test_31_actual_reference_times_bounded_without_conversion(self):
        d = json.loads((ROOT / "evidence/local-selected-action-events.json").read_text(encoding="utf-8"))
        rows = [ref for r in d["records"] for ref in r["anim_events"]["info_event_references"]]
        self.assertEqual(len(rows), 48)
        self.assertEqual(sum(ref["eventCount"] for ref in rows), 60)
        for r in d["records"]:
            for ref in r["anim_events"]["info_event_references"]:
                self.assertGreaterEqual(ref["time_raw"], 0)
                self.assertLess(ref["time_raw"], r["anim_events"]["header"]["length_raw"])
    def test_32_tlsa_preserves_sentinel_and_per_reference_scope(self):
        d = json.loads((ROOT / "evidence/local-selected-action-channels.json").read_text(encoding="utf-8"))
        records = [r["tlsa"] for r in d["records"] if "tlsa" in r]
        self.assertEqual([r["version"] for r in records], [7, 10])
        self.assertEqual([sum(len(c["animations"]) for g in r["selected_groups"] for c in g["choices"]) for r in records], [13, 128])
        for r in records:
            for g in r["selected_groups"]:
                self.assertEqual(g["blendInTime"], -1)
                for c in g["choices"]:
                    self.assertTrue(all(a["duration"] == -1 and a["durationScale"] == 1 for a in c["animations"]))
    def test_33_gait6_slots_do_not_supply_limb_identity(self):
        d = json.loads((ROOT / "evidence/local-selected-movement-resources.json").read_text(encoding="utf-8"))
        selected = [r for r in d["records"] if r["name"] == "gait6"]
        self.assertEqual(len(selected), 2)
        for r in selected:
            g = r["gait_summary"]
            self.assertEqual(len(g["stepLengthKeys"]), 8)
            self.assertEqual([k["speedi"] for k in g["stepLengthKeys"]], [0, 2.5, 4, 5.5, 6.5, 7.5, 8.5, 10])
            self.assertTrue(all(len(k["triggers"]) == len(k["dutyFactors"]) == 6 for k in g["gaitGroupKeys"]))
    def test_34_manifest_has_explicit_consumer_unknowns(self):
        m = json.loads((ROOT / "evidence/public-animation-clock-contracts.json").read_text(encoding="utf-8"))
        self.assertFalse(m["target_runtime_verified"])
        self.assertIsNone(m["rea_evidence_id"])
        self.assertIn("INFO_time_to_seconds", m["unresolved"])
        self.assertIn("TLSA_durationScale_consumer_formula", m["unresolved"])


class CompleteScenarioTests(unittest.TestCase):
    def test_35_six_leg_swing_pause_double_rate_and_emergency_stop_table(self):
        a, g = Action(), Gait()
        world = F(0)
        rows = []
        for tick, endpoint in enumerate([F(1, 5), F(35, 100), F(2, 5), F(3, 5), F(725, 1000), F(9, 10)]):
            dt = endpoint - world
            a.step(dt, tick); g.advance_distance(2 * dt)
            rows.append((endpoint, a.elapsed, g.cycles))
            if endpoint == F(2, 5): a.paused = True
            if endpoint == F(3, 5): a.paused = False; a.rate = 2
            world = endpoint
        self.assertEqual(rows, [(F(1, 5), F(1, 5), F(2, 5)),
                                (F(35, 100), F(35, 100), F(7, 10)),
                                (F(2, 5), F(2, 5), F(4, 5)),
                                (F(3, 5), F(2, 5), F(6, 5)),
                                (F(725, 1000), F(65, 100), F(29, 20)),
                                (F(9, 10), F(1), F(9, 5))])
        self.assertEqual(a.emitted, ["hit", "recover"])
        self.assertEqual(a.state, "Completed")
        g.emergency_stop(); g.settle(.15)
        self.assertEqual((g.mode, g.cycles, sum(g.contacts())), ("Stopped", F(9, 5), 6))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps({"kind": "independent-animation-clock-examples", "tests_run": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors),
                      "success": result.wasSuccessful(),
                      "counts": {"action_visual_clocks": 20, "gait_geometry": 8, "complete_scenario": 1, "reused_evidence": 6},
                      "game_runtime_verified": False}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
