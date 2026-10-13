"""Executable independent examples for studies 20-22; not Spore code/tests.

Checks arithmetic and sequential event invariants only. It does not model
pathfinding, real animation events, persistence or concurrent transactions.
"""

from dataclasses import dataclass, field
import unittest


@dataclass
class PopulationExample:
    target: int = 6
    residents: set[str] = field(default_factory=lambda: {"a", "b", "c"})
    away: set[str] = field(default_factory=lambda: {"d"})
    births: int = 1
    generation: int = 1
    active: bool = True
    reservations: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {"initial": (1, 1)}
    )
    deaths: set[tuple[str, int]] = field(default_factory=set)
    credited_kills: int = 0

    def allocated(self) -> int:
        return (
            len(self.residents)
            + len(self.away)
            + self.births
            + sum(count for _, count in self.reservations.values())
        )

    def reserve(self, job: str, available: int) -> int:
        if job in self.reservations:
            raise ValueError("job identity already reserved")
        count = min(max(0, self.target - self.allocated()), available)
        if self.active and count > 0:
            self.reservations[job] = (self.generation, count)
            return count
        return 0

    def death(self, entity: str, incarnation: int) -> str:
        key = (entity, incarnation)
        if key in self.deaths:
            return "Duplicate"
        if entity not in self.residents | self.away:
            raise ValueError("death must belong to a living allocated member")
        self.residents.discard(entity)
        self.away.discard(entity)
        self.deaths.add(key)
        self.credited_kills += 1
        return "Committed"

    def complete(self, job: str, created: list[str]) -> str:
        reservation = self.reservations.get(job)
        if reservation is None:
            return "MissingOrAlreadyConsumed"
        generation, count = reservation
        if len(set(created)) != len(created) or len(created) > count:
            raise ValueError("invalid creation result")
        if set(created) & (self.residents | self.away):
            raise ValueError("created entity identity is already allocated")
        del self.reservations[job]
        if not self.active or generation != self.generation:
            return "DiscardStale"
        self.residents.update(created)
        return "Installed"


@dataclass
class RoleExample:
    capacity: int = 1
    claims: dict[str, tuple[int, int]] = field(default_factory=dict)

    def claim(self, actor: str, body: int, controller: int) -> str:
        if actor in self.claims:
            return "AlreadyClaimed"
        if len(self.claims) >= self.capacity:
            return "Full"
        self.claims[actor] = (body, controller)
        return "Reserved"

    def invalidate(self, actor: str) -> None:
        self.claims.pop(actor, None)


@dataclass
class SocialExample:
    round_id: int = 1
    versions: dict[str, int] = field(default_factory=lambda: {"a": 1, "b": 1})
    contributions: dict[tuple[int, str], float] = field(default_factory=dict)
    committed_outcomes: set[str] = field(default_factory=set)
    impressed: set[str] = field(default_factory=set)

    def submit(self, round_id: int, actor: str, body: int, strength: float) -> str:
        if round_id != self.round_id:
            return "WrongRound"
        if actor not in self.versions or body != self.versions[actor]:
            return "StaleBodyOrAbsentActor"
        key = (round_id, actor)
        if key in self.contributions:
            return "Duplicate"
        self.contributions[key] = strength
        return "Accepted"

    def strength(self) -> float:
        return sum(
            value for (round_id, _), value in self.contributions.items()
            if round_id == self.round_id
        )

    def commit_success(self, session: str, target: str) -> str:
        if session in self.committed_outcomes:
            return "DuplicateOutcome"
        self.committed_outcomes.add(session)
        if target in self.impressed:
            return "AlreadyImpressed"
        self.impressed.add(target)
        return "NewRelationshipProgress"


class GroupSocialExamples(unittest.TestCase):
    def test_population_budget_counts_away_births_and_pending_jobs(self):
        herd = PopulationExample()
        self.assertEqual(herd.allocated(), 6)
        self.assertEqual(herd.reserve("unneeded", 5), 0)
        self.assertEqual(herd.death("a", 1), "Committed")
        self.assertEqual(herd.allocated(), 5)
        self.assertEqual(herd.reserve("refill", 5), 1)
        self.assertEqual(herd.reserve("another", 5), 0)
        self.assertEqual(herd.allocated(), 6)
        self.assertEqual(herd.complete("refill", ["e"]), "Installed")
        self.assertEqual(herd.allocated(), 6)
        self.assertEqual(herd.complete("refill", ["e"]), "MissingOrAlreadyConsumed")

    def test_extinction_rejects_old_spawn_and_disables_new_reservations(self):
        herd = PopulationExample()
        herd.active = False
        herd.generation += 1
        self.assertEqual(herd.complete("initial", ["e"]), "DiscardStale")
        self.assertNotIn("e", herd.residents)
        self.assertEqual(herd.reserve("after-extinction", 5), 0)

    def test_death_progress_is_idempotent(self):
        herd = PopulationExample()
        herd.credited_kills = 6
        self.assertEqual(herd.death("a", 1), "Committed")
        self.assertEqual(herd.death("a", 1), "Duplicate")
        self.assertEqual(herd.credited_kills, 7)

    def test_role_capacity_and_body_change_release(self):
        role = RoleExample()
        self.assertEqual(role.claim("a", 1, 1), "Reserved")
        self.assertEqual(role.claim("b", 1, 1), "Full")
        role.invalidate("a")
        self.assertEqual(role.claim("b", 1, 1), "Reserved")
        self.assertEqual(role.claim("b", 1, 1), "AlreadyClaimed")

    def test_social_unique_contribution_and_round_arithmetic(self):
        social = SocialExample()
        self.assertEqual(social.submit(1, "a", 1, 3), "Accepted")
        self.assertEqual(social.submit(1, "b", 1, 2), "Accepted")
        self.assertEqual(social.submit(1, "b", 1, 2), "Duplicate")
        self.assertEqual(social.strength(), 5)
        self.assertGreaterEqual(social.strength(), 4)
        self.assertEqual(social.strength() * 0, 0)
        self.assertLess(social.strength() * 0, 4)
        social.round_id = 2
        self.assertEqual(social.submit(1, "b", 1, 2), "WrongRound")
        self.assertEqual(social.submit(2, "a", 1, 3), "Accepted")
        self.assertEqual(social.strength(), 3)

    def test_part_loss_before_effect_commit_rejects_contribution(self):
        social = SocialExample()
        social.versions["b"] = 2
        self.assertEqual(social.submit(1, "a", 1, 3), "Accepted")
        self.assertEqual(social.submit(1, "b", 1, 2), "StaleBodyOrAbsentActor")
        self.assertEqual(social.strength(), 3)
        self.assertLess(social.strength(), 4)

    def test_relationship_outcome_and_individual_progress_deduplicate(self):
        social = SocialExample()
        self.assertEqual(social.commit_success("s1", "c"), "NewRelationshipProgress")
        self.assertEqual(social.commit_success("s1", "c"), "DuplicateOutcome")
        self.assertEqual(social.commit_success("s2", "c"), "AlreadyImpressed")
        for i in range(3):
            social.commit_success(f"other-{i}", f"target-{i}")
        self.assertEqual(len(social.impressed), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
