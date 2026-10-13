"""Independent reference checks for docs 16-17; not a game implementation."""
import json
import math
import re
import unittest
from pathlib import Path


def utility(damage, protection, risk, cost, duration):
    return damage / 30 + 1.5 * protection / 30 - risk / 30 - .25 * cost - .05 * duration


# (name, D, B, R, K, T, documented U); fixture inputs are not calibrated predictions.
GROUPS = [
    [("bolt-C", 25.5, 20.4, 6, 1, 1.3, 1.355),
     ("pulse-C", 7.2, 21.6, 6, .5, .4, .975),
     ("ward-A", 0, 19, 3, .75, .6, .6325),
     ("bolt-G", 25.5, 0, 6, 1, 1.3, .335),
     ("needle-C", 21.6, 0, 6, .9, .7, .26),
     ("claw-G", 21.6, 0, 12, .6, .8, .13),
     ("retreat", 0, 0, 2, 0, 1, -.1167)],
    [("pulse-C", 7.2, 21.6, 0, .5, .4, 1.175),
     ("ward-A", 0, 19, 0, .75, .6, .7325),
     ("needle-C", 21.6, 0, 0, .9, .7, .46)],
    [("needle-C", 19.8, 21.6, 0, .9, .7, 1.48),
     ("ward-A", 0, 19, 0, .75, .6, .7325),
     ("horn-G", 28.8, 0, 0, 1, 1.1, .655),
     ("bite-G", 25.2, 0, 0, .8, .9, .595),
     ("needle-G", 21.6, 0, 0, .9, .7, .46)],
    [("bite-G", 25.2, 0, 0, .8, .9, .595),
     ("wait-horn-G", 25.2, 0, 0, 1, 1.8, .5),
     ("needle-G", 21.6, 0, 0, .9, .7, .46),
     ("pulse-G", 7.2, 0, 0, .5, .4, .095)],
]

# (soul cost, body cost, windup, recovery, cooldown, damage, required capability)
SKILLS = {
    "bolt": (20, 0, 1, .3, 2, 30, "sigil"),
    "pulse": (10, 0, .2, .2, 2, 8, None),
    "needle": (18, 0, .4, .3, 1, 24, None),
    "horn": (0, 10, .8, .3, 1, 32, "horn"),
    "bite": (0, 8, .5, .4, 1, 28, "mouth"),
}


class ReferenceState:
    """Single-slot fixture with explicit owner keys and effect-time costs."""
    def __init__(self):
        self.body, self.generation = "B1", 7
        self.resources = {"S": 55, "B1": 30, "B2": 80}
        self.health = {"C": 30, "G": 60, "A": 24, "B1": 80, "B2": 120}
        self.parts = {"B1": {"RF": "sigil", "LF": "sigil"},
                      "B2": {"H": "horn", "M": "mouth"}}
        self.actions, self.reservations, self.cooldowns = {}, {}, {}
        self.active = None
        self.threats = {"original-C": 1.3, "next-G": 4.3}

    def available(self, owner):
        return self.resources[owner] - sum(cost for wallet, cost in self.reservations.values() if wallet == owner)

    def start(self, action_id, skill, target, part, now):
        if self.active is not None:
            return "SlotBusy"
        sc, bc, wind, recovery, cooldown, damage, capability = SKILLS[skill]
        owner = "S" if sc else self.body
        if now + 1e-9 < self.cooldowns.get((owner, skill), 0):
            return "Cooldown"
        if self.health[target] <= 0:
            return "TargetDead"
        if capability and self.parts[self.body].get(part) != capability:
            return "ProviderUnavailable"
        if part == "LF" and now < .8:
            return "ChannelBusy"
        costs = [("S", sc), (self.body, bc)]
        if any(self.available(wallet) < cost for wallet, cost in costs):
            return "ResourceInsufficient"
        for wallet, cost in costs:
            if cost:
                self.reservations[(action_id, wallet)] = wallet, cost
        self.actions[action_id] = dict(skill=skill, target=target, part=part,
            body=self.body, generation=self.generation, phase="Windup", committed=False,
            effect=now + wind, end=now + wind + recovery, owner=owner)
        self.active = action_id
        return "Started"

    def cancel(self, action_id):
        action = self.actions[action_id]
        if action["phase"] in {"Cancelled", "Completed"}:
            return "AlreadyTerminated"
        for token in list(self.reservations):
            if token[0] == action_id:
                del self.reservations[token]
        action["phase"] = "Cancelled"
        if self.active == action_id:
            self.active = None
        return "Cancelled"

    def sever(self, part):
        self.parts[self.body].pop(part, None)
        for aid, action in self.actions.items():
            if action["body"] == self.body and action["part"] == part:
                self.cancel(aid)

    def transfer(self, body):
        if body not in self.parts:
            return "NewBodyUnavailable"
        if self.active is not None:
            self.cancel(self.active)
        self.body = body
        self.generation += 1
        return "Transferred"

    def commit(self, action_id, now, hit=True):
        action = self.actions[action_id]
        if action["committed"]:
            return "DuplicateIgnored"
        if action["phase"] != "Windup":
            return "ActionNotActive"
        if (action["body"], action["generation"]) != (self.body, self.generation):
            self.cancel(action_id)
            return "StaleLease"
        if now + 1e-9 < action["effect"]:
            return "TooEarly"
        skill = action["skill"]
        sc, bc, wind, recovery, cooldown, damage, capability = SKILLS[skill]
        if capability and self.parts[self.body].get(action["part"]) != capability:
            self.cancel(action_id)
            return "ProviderUnavailable"
        if self.health[action["target"]] <= 0:
            self.cancel(action_id)
            return "TargetDead"
        for token in list(self.reservations):
            if token[0] == action_id:
                wallet, cost = self.reservations.pop(token)
                self.resources[wallet] -= cost
        if hit:
            target = action["target"]
            self.health[target] = max(0, self.health[target] - damage)
            if skill == "pulse" and target == "C":
                self.threats.pop("original-C", None)
                self.threats["predicted-next-C"] = now + 1.2 + 1.4
            if self.health[target] == 0:
                for threat in list(self.threats):
                    if threat.endswith(target):
                        del self.threats[threat]
        self.cooldowns[(action["owner"], skill)] = now + cooldown
        action["committed"], action["phase"] = True, "Recovery"
        return "Committed"

    def complete(self, action_id, now):
        action = self.actions[action_id]
        if action["phase"] != "Recovery" or now + 1e-9 < action["end"]:
            return "NotReady"
        action["phase"] = "Completed"
        if self.active == action_id:
            self.active = None
        return "Completed"


class BattleChecks(unittest.TestCase):
    def test_scores_match_document_and_choices(self):
        expected_choices = ["bolt-C", "pulse-C", "needle-C", "bite-G"]
        scores = []
        for group, expected_choice in zip(GROUPS, expected_choices):
            for name, d, b, r, k, t, expected in group:
                actual = utility(d, b, r, k, t)
                self.assertAlmostEqual(actual, expected, delta=.00005, msg=name)
                scores.append(expected)
            self.assertEqual(max(group, key=lambda row: utility(*row[1:6]))[0], expected_choice)
        doc = Path(__file__).parents[1] / "17-soul-ai-complete-battle.md"
        documented = []
        for line in doc.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            last = line.split("|")[-2].strip().replace("**", "")
            if re.fullmatch(r"-?\d*\.\d{4}", last):
                documented.append(float(last))
        self.assertEqual(documented, scores, "All 19 numeric table rows must remain aligned")

    def test_geometry_and_provider_specific_level(self):
        self.assertLessEqual(math.dist((0, .4), (1.5, .4)), 1.6)
        self.assertGreater(math.dist((0, -.4), (1.5, .4)), 1.2)
        self.assertGreater(math.dist((0, .4), (6, .4)), 1.6)
        self.assertLessEqual(math.dist((0, .4), (6, .4)), 8)
        self.assertEqual(.9 * min(24, 22), 19.8)
        # The low-level LF remains 16, never RF's 24.
        levels = {"RF": 24, "LF": 16}
        del levels["RF"]
        self.assertEqual(levels["LF"], 16)

    def test_complete_trace(self):
        s = ReferenceState()
        self.assertEqual(s.start("X", "bolt", "C", "RF", 0), "Started")
        self.assertEqual((s.resources["S"], s.available("S")), (55, 35))
        self.assertEqual(s.start("conflict", "needle", "C", None, .1), "SlotBusy")
        s.health["B1"] -= 12
        s.sever("RF")
        self.assertEqual((s.health["C"], s.available("S")), (30, 55))
        self.assertNotIn(("S", "bolt"), s.cooldowns)
        self.assertEqual(s.start("left", "bolt", "C", "LF", .4), "ChannelBusy")
        self.assertEqual(s.start("P", "pulse", "C", None, .4), "Started")
        self.assertEqual(s.commit("P", .6), "Committed")
        self.assertEqual((s.health["C"], s.resources["S"]), (22, 45))
        self.assertNotIn("original-C", s.threats)
        self.assertAlmostEqual(s.threats["predicted-next-C"], 3.2)
        self.assertEqual(s.complete("P", .8), "Completed")
        self.assertEqual(s.transfer("B2"), "Transferred")
        self.assertEqual(s.generation, 8)
        self.assertEqual(s.start("no-hand", "bolt", "C", "RF", .8), "ProviderUnavailable")
        self.assertEqual(s.start("no-reset", "pulse", "C", None, .8), "Cooldown")
        self.assertEqual(s.start("N", "needle", "C", None, .8), "Started")
        self.assertEqual(s.available("S"), 27)
        self.assertEqual(s.commit("X", 1), "ActionNotActive")
        self.assertEqual(s.commit("N", 1.2), "Committed")
        self.assertEqual(s.commit("N", 1.2), "DuplicateIgnored")
        self.assertEqual((s.health["C"], s.resources["S"]), (0, 27))
        self.assertEqual(s.complete("N", 1.5), "Completed")
        self.assertEqual(s.start("H", "horn", "G", "H", 1.5), "Started")
        self.assertEqual(s.commit("H", 2.3), "Committed")
        self.assertEqual((s.health["G"], s.resources["B2"]), (28, 70))
        self.assertEqual(s.complete("H", 2.6), "Completed")
        self.assertEqual(s.start("early-H", "horn", "G", "H", 2.6), "Cooldown")
        self.assertEqual(s.start("B", "bite", "G", "M", 2.6), "Started")
        self.assertEqual(s.commit("B", 3.1), "Committed")
        self.assertEqual(s.complete("B", 3.5), "Completed")
        self.assertEqual(s.resources, {"S": 27, "B1": 30, "B2": 62})
        self.assertEqual(s.health, {"C": 0, "G": 0, "A": 24, "B1": 68, "B2": 120})
        self.assertEqual(s.reservations, {})
        self.assertEqual(s.threats, {})

    def test_miss_pays_and_committed_effect_survives_transfer(self):
        s = ReferenceState()
        self.assertEqual(s.start("N", "needle", "C", None, 0), "Started")
        self.assertEqual(s.commit("N", .4, hit=False), "Committed")
        self.assertEqual((s.health["C"], s.resources["S"]), (30, 37))
        self.assertEqual(s.transfer("B2"), "Transferred")
        self.assertEqual(s.resources["S"], 37)
        self.assertEqual(s.start("retry", "needle", "C", None, .8), "Cooldown")
        self.assertEqual(s.commit("N", .8), "DuplicateIgnored")
        self.assertEqual(s.health["C"], 30)

    def test_owner_tokens_and_stale_lease(self):
        s = ReferenceState()
        self.assertEqual(s.start("X", "bolt", "C", "RF", 0), "Started")
        s.generation += 1  # Simulate an independently revoked lease.
        self.assertEqual(s.commit("X", 1), "StaleLease")
        self.assertEqual(s.resources["S"], 55)
        self.assertEqual(s.cancel("X"), "AlreadyTerminated")
        self.assertEqual(s.transfer("B2"), "Transferred")
        self.assertEqual(s.start("new", "horn", "G", "H", 1.1), "Started")
        self.assertEqual(s.cancel("X"), "AlreadyTerminated")
        self.assertEqual(s.available("B2"), 70)
        self.assertEqual(s.resources["B1"], 30)
        self.assertEqual(s.transfer("absent"), "NewBodyUnavailable")
        self.assertEqual(s.body, "B2")
        self.assertEqual(s.active, "new")

    def test_insufficient_resource_and_unrelated_part(self):
        s = ReferenceState()
        s.resources["S"] = 19
        self.assertEqual(s.start("X", "bolt", "C", "RF", 0), "ResourceInsufficient")
        self.assertEqual(s.reservations, {})
        s.resources["S"] = 55
        self.assertEqual(s.start("X", "bolt", "C", "RF", 0), "Started")
        s.sever("LF")
        self.assertEqual(s.actions["X"]["phase"], "Windup")
        self.assertEqual(s.commit("X", 1), "Committed")
        self.assertEqual(s.health["C"], 0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BattleChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"reference_tests": result.testsRun, "success": result.wasSuccessful(),
                      "score_rows": sum(map(len, GROUPS)), "scope": "independent document fixture"}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
