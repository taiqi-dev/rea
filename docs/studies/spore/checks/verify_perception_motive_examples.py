"""Independent design examples, not Spore behavior or production AI tests."""
from dataclasses import dataclass
import math
import unittest


@dataclass(frozen=True)
class Observation:
    event_id: str
    observed_at: float
    received_at: float
    source: str
    position: tuple
    confidence: float
    error_radius: float
    stamp: tuple = (1, 1)


class Belief:
    def __init__(self):
        self.seen_events = set()
        self.observations = []

    def accept(self, obs, now, active_stamp):
        if obs.observed_at > obs.received_at or obs.received_at > now:
            return 'InvalidTimestamp'
        if not 0 <= obs.confidence <= 1 or obs.error_radius < 0:
            return 'InvalidEstimate'
        if obs.source in ('visual', 'soul_reveal') and obs.stamp != active_stamp:
            return 'StaleSensor'
        if obs.event_id in self.seen_events:
            return 'Duplicate'
        self.seen_events.add(obs.event_id)
        self.observations.append(obs)
        return 'Accepted'

    def best(self, now):
        active = [o for o in self.observations if 0 <= now - o.observed_at < 8]
        return max(active, key=lambda o: o.confidence * math.exp(-(now-o.observed_at)/4), default=None)

    def estimate(self, now):
        o = self.best(now)
        if o is None:
            return None
        age = now - o.observed_at
        return dict(position=o.position, confidence=o.confidence * math.exp(-age/4),
                    error_radius=o.error_radius + 2*age, source=o.source)

    def targetable(self, now, stamp):
        return any(o.source in ('visual', 'soul_reveal') and o.stamp == stamp
                   and 0 <= now-o.observed_at <= .2 and o.error_radius <= .25
                   for o in self.observations)


def scores(hunger, injury, danger, win, confidence, escape_cost=.2):
    return dict(Fight=80*win*confidence-50*injury-20*hunger,
                Investigate=45*confidence-25*danger-10*injury,
                Flee=80*danger+40*injury-20*escape_cost,
                Eat=60*hunger-70*danger)


def choose(values, legal, incumbent=None, hold_done=True, margin=8):
    candidates = {n: values[n] for n in legal}
    if not candidates:
        return 'NoLegalPlan'
    best = max(candidates, key=lambda n: (candidates[n], n))
    if incumbent in candidates and (not hold_done or candidates[best] < candidates[incumbent]+margin):
        return incumbent
    return best


class PerceptionExamples(unittest.TestCase):
    def obs(self, **kw):
        return Observation(**(dict(event_id='v1', observed_at=2, received_at=2,
                                   source='visual', position=(20, 0), confidence=1,
                                   error_radius=.1) | kw))

    def test_lost_target_position_freezes_and_uncertainty_grows(self):
        b=Belief(); b.accept(self.obs(), 2, (1, 1))
        e=b.estimate(4)
        self.assertEqual(e['position'], (20, 0))
        self.assertAlmostEqual(e['confidence'], math.exp(-.5))
        self.assertAlmostEqual(e['error_radius'], 4.1)
        self.assertFalse(b.targetable(4, (1, 1)))

    def test_report_delay_does_not_reset_observation_clock(self):
        b=Belief(); b.accept(self.obs(source='report', received_at=7), 7, (1, 1))
        self.assertIsNone(b.estimate(10))

    def test_repeated_report_does_not_refresh_memory(self):
        b=Belief(); o=self.obs(source='report')
        self.assertEqual(b.accept(o, 2, (1,1)), 'Accepted')
        self.assertEqual(b.accept(o, 7, (1,1)), 'Duplicate')
        self.assertEqual(len(b.observations), 1)

    def test_fresh_hearing_is_not_precise_attack_lock(self):
        b=Belief(); b.accept(self.obs(source='hearing', error_radius=4), 2, (1,1))
        self.assertFalse(b.targetable(2, (1,1)))
        self.assertEqual(b.estimate(2)['error_radius'], 4)

    def test_body_or_control_change_invalidates_current_sensing_only(self):
        b=Belief(); b.accept(self.obs(), 2, (1,1))
        self.assertFalse(b.targetable(2.1, (2,1)))
        self.assertFalse(b.targetable(2.1, (1,2)))
        self.assertIsNotNone(b.estimate(2.1))
        self.assertEqual(b.accept(self.obs(event_id='late'),2.1,(2,1)), 'StaleSensor')

    def test_declared_soul_reveal_can_target_with_new_body(self):
        b=Belief(); b.accept(self.obs(source='soul_reveal', stamp=(2,2)), 2, (2,2))
        self.assertTrue(b.targetable(2, (2,2)))

    def test_future_events_rejected_instead_of_negative_decay(self):
        b=Belief()
        self.assertEqual(b.accept(self.obs(observed_at=3),2,(1,1)), 'InvalidTimestamp')
        self.assertEqual(b.accept(self.obs(received_at=4),3,(1,1)), 'InvalidTimestamp')

    def test_confidence_selects_source_without_destroying_source_history(self):
        b=Belief(); b.accept(self.obs(),2,(1,1))
        b.accept(self.obs(event_id='r',source='report',observed_at=3,received_at=3,
                          position=(40,0),confidence=.2,error_radius=5),3,(1,1))
        self.assertEqual(b.estimate(3)['position'], (20,0))
        self.assertEqual(len(b.observations),2)

    def test_encounter_start_lost_ambush_recovery_reacquire(self):
        self.assertEqual(choose(scores(.7,.1,.2,.85,1),{'Fight','Flee','Eat'}), 'Fight')
        self.assertEqual(choose(scores(.7,.1,.2,.85,math.exp(-.5)),
                                {'Investigate','Flee'},'Fight'), 'Investigate')
        self.assertEqual(choose(scores(.7,.65,.8,.85,math.exp(-.75)),
                                {'Investigate','Flee'},'Investigate'), 'Flee')
        self.assertEqual(choose(scores(.8,.45,.15,.5,0),{'Flee','Eat'},'Flee'), 'Eat')
        self.assertEqual(choose(scores(.3,.2,.45,.35,1),{'Fight','Flee','Eat'},'Eat'), 'Flee')

    def test_hysteresis_and_invalid_incumbent(self):
        values={'Fight':50,'Flee':55}
        self.assertEqual(choose(values,{'Fight','Flee'},'Fight'), 'Fight')
        self.assertEqual(choose(values,{'Flee'},'Fight',hold_done=False), 'Flee')
        self.assertEqual(choose(values,{'Fight','Flee'},'Fight',hold_done=False,margin=0),'Fight')

    def test_critical_survival_filter_and_blocked_escape(self):
        values={'Fight':99,'Flee':10,'Eat':9}
        self.assertEqual(choose(values,{'Flee'}), 'Flee')
        self.assertEqual(choose(values,set()), 'NoLegalPlan')
        # No route means flee is not legal: explicitly allow last-resort defense.
        self.assertEqual(choose(values,{'Fight'}), 'Fight')


if __name__ == '__main__':
    unittest.main(verbosity=2)
