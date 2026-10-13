"""Independent editor transaction/budget/LOD examples; not Spore implementation."""
from dataclasses import dataclass, replace
import hashlib
import math
import unittest


@dataclass(frozen=True)
class Part:
    id: str
    parent: str | None
    dna: int
    complexity: int
    bones: int
    vertices: int
    scale: float = 1.0


CAPS = (96, 50, 9000)


def example_body():
    parts = [Part('body', None, 100, 12, 6, 2400)]
    parts += [Part(f'leg{i}', 'body', 30, 8, 4, 600) for i in range(6)]
    parts += [Part('mouth', 'body', 40, 6, 2, 400)]
    parts += [Part(f'arm{i}', 'body', 25, 5, 3, 350) for i in range(4)]
    parts += [Part(f'eye{i}', 'body', 5, 1, 1, 100) for i in range(2)]
    return tuple(parts)


def totals(parts):
    return tuple(sum(getattr(p, field) for p in parts)
                 for field in ('dna', 'complexity', 'bones', 'vertices'))


def reasons(parts, available_dna, caps=CAPS):
    errors = []
    ids = [p.id for p in parts]
    if len(set(ids)) != len(ids):
        errors.append('DuplicatePartId')
    if sum(p.parent is None for p in parts) != 1:
        errors.append('RootCount')
    by_id = {p.id: p for p in parts}
    for p in parts:
        if not math.isfinite(p.scale) or p.scale <= 0:
            errors.append('InvalidScale')
        if any(type(x) is not int or x < 0 for x in
               (p.dna, p.complexity, p.bones, p.vertices)):
            errors.append('InvalidCatalogCost')
        if p.parent is not None and p.parent not in by_id:
            errors.append('MissingParent')
        visited = set()
        cursor = p.id
        while cursor is not None and cursor in by_id:
            if cursor in visited:
                errors.append('AttachmentCycle')
                break
            visited.add(cursor)
            cursor = by_id[cursor].parent
    if 'InvalidCatalogCost' not in errors:
        dna, complexity, bones, vertices = totals(parts)
        if dna > available_dna:
            errors.append('DNAInsufficient')
        for value, cap, error in zip((complexity, bones, vertices), caps,
                                     ('ComplexityExceeded', 'BonesExceeded', 'GeometryExceeded')):
            if value > cap:
                errors.append(error)
    return tuple(dict.fromkeys(errors))


def fingerprint(parts):
    # Deliberately includes ordering and shape; production uses canonical typed serialization.
    return hashlib.sha256(repr(tuple(parts)).encode('utf-8')).hexdigest()


class Editor:
    def __init__(self, parts, balance=70, revision=42):
        self.parts = tuple(parts)
        self.balance = balance
        self.revision = revision
        self.actions = {}
        self.installed = None
        self.compile_error = None
        self.leases = set()

    def commit(self, candidate, expected_revision, action_id):
        candidate = tuple(candidate)
        digest = fingerprint(candidate)
        if action_id in self.actions:
            original_digest, result = self.actions[action_id]
            if original_digest != digest:
                raise ValueError('ActionPayloadConflict')
            return result
        if self.revision != expected_revision:
            raise ValueError('StaleEditorRevision')
        errors = reasons(candidate, self.balance + totals(self.parts)[0])
        if errors:
            raise ValueError(','.join(errors))
        self.balance += totals(self.parts)[0] - totals(candidate)[0]
        self.parts = candidate
        self.revision += 1
        self.compile_error = None
        self.actions[action_id] = (digest, self.revision)
        return self.revision

    def job_key(self):
        return (self.revision, fingerprint(self.parts), 'catalog-v1', 'algorithm-v1', 'HQ')

    def start_job(self, lease):
        if lease in self.leases:
            raise ValueError('DuplicateLease')
        self.leases.add(lease)
        return self.job_key()

    def finish_job(self, lease, key, products, error=None):
        if lease not in self.leases:
            return 'DuplicateOrCancelled'
        self.leases.remove(lease)
        if key != self.job_key():
            return 'Stale'
        if error:
            self.compile_error = error
            return 'Failed'
        if set(products) != {'skin', 'bind', 'texture'} or any(v != key for v in products.values()):
            self.compile_error = 'MixedArtifactVersions'
            return 'Failed'
        self.installed = key
        return 'Installed'


LOD = {'high': (60, 8000, 46, 4), 'mid': (20, 3000, 32, 4), 'low': (5, 900, 18, 2)}


def visual_cost(level):
    frequency, vertices, palette, influences = LOD[level]
    return {'ik': (6 * 4 + 4 * 2) * frequency,
            'matrices': palette * frequency,
            'weighted_vertex_products': vertices * influences * 60}


def authority_at(time):
    phase = (2 * time) % 1
    contacts = tuple((phase + i / 6) % 1 < .6 for i in range(6))
    return {'phase': phase, 'contacts': contacts, 'feet': 6,
            'mouth_tip': (math.cos(time), math.sin(time)),
            'hit_event_due': .25 <= time < .25 + 1 / 60}


def frame(time, level):
    return {'authority': authority_at(time), 'visual_cost': visual_cost(level)}


class EditorBudgetExamples(unittest.TestCase):
    def test_complete_four_arm_six_leg_accounting(self):
        self.assertEqual(totals(example_body()), (430, 88, 46, 8000))
        self.assertEqual(reasons(example_body(), 500), ())

    def test_affordable_pair_rejected_without_partial_payment(self):
        e = Editor(example_body())
        candidate = e.parts + (Part('leg6', 'body', 30, 8, 4, 600), Part('leg7', 'body', 30, 8, 4, 600))
        self.assertEqual(totals(candidate), (490, 104, 54, 9200))
        self.assertEqual(reasons(candidate, 500), ('ComplexityExceeded', 'BonesExceeded', 'GeometryExceeded'))
        before = e.parts, e.balance, e.revision
        with self.assertRaisesRegex(ValueError, 'ComplexityExceeded'):
            e.commit(candidate, 42, 'pair')
        self.assertEqual((e.parts, e.balance, e.revision), before)

    def test_geometry_legal_but_dna_insufficient(self):
        candidate = example_body() + (Part('armor', 'body', 80, 3, 0, 300),)
        self.assertEqual(totals(candidate), (510, 91, 46, 8300))
        self.assertEqual(reasons(candidate, 500), ('DNAInsufficient',))

    def test_exact_boundaries_and_each_one_over(self):
        p = Part('body', None, 500, 96, 50, 9000)
        self.assertEqual(reasons((p,), 500), ())
        for field, error in [('dna', 'DNAInsufficient'), ('complexity', 'ComplexityExceeded'),
                             ('bones', 'BonesExceeded'), ('vertices', 'GeometryExceeded')]:
            with self.subTest(field=field):
                self.assertEqual(reasons((replace(p, **{field: getattr(p, field) + 1}),), 500), (error,))

    def test_graph_identity_cycles_and_invalid_catalog_input(self):
        body = example_body()
        cases = [(body + (body[-1],), 'DuplicatePartId'),
                 (body + (Part('orphan', 'missing', 0, 0, 0, 0),), 'MissingParent'),
                 (body + (Part('x', 'y', 0, 0, 0, 0), Part('y', 'x', 0, 0, 0, 0)), 'AttachmentCycle'),
                 ((replace(body[0], scale=float('nan')),), 'InvalidScale'),
                 ((replace(body[0], dna=-1),), 'InvalidCatalogCost')]
        for candidate, error in cases:
            with self.subTest(error=error):
                self.assertIn(error, reasons(candidate, 500))

    def test_replacement_and_undo_preserve_external_dna(self):
        e = Editor(example_body())
        initial = e.parts
        changed = tuple(Part('wing', 'body', 35, 4, 2, 400) if p.id == 'arm0' else p for p in initial)
        self.assertEqual(totals(changed), (440, 87, 45, 8050))
        e.commit(changed, 42, 'replace')
        self.assertEqual(e.balance, 60)
        e.balance += 7  # An external reward cannot be erased by undo history.
        e.commit(initial, 43, 'undo')
        self.assertEqual((e.balance, e.revision), (77, 44))

    def test_revision_recheck_idempotency_and_payload_conflict(self):
        e = Editor(example_body())
        reduced = tuple(p for p in e.parts if p.id != 'arm0')
        self.assertEqual(e.commit(reduced, 42, 'remove'), 43)
        self.assertEqual(e.commit(reduced, 42, 'remove'), 43)
        self.assertEqual(e.balance, 95)
        with self.assertRaisesRegex(ValueError, 'StaleEditorRevision'):
            e.commit(example_body(), 42, 'different')
        with self.assertRaisesRegex(ValueError, 'ActionPayloadConflict'):
            e.commit(example_body(), 43, 'remove')

    def test_superseded_compile_and_duplicate_completion_release_once(self):
        e = Editor(example_body())
        key = e.start_job('old')
        e.commit(tuple(p for p in e.parts if p.id != 'arm0'), 42, 'remove')
        self.assertEqual(e.finish_job('old', key, dict.fromkeys(('skin', 'bind', 'texture'), key)), 'Stale')
        self.assertEqual(e.finish_job('old', key, {}), 'DuplicateOrCancelled')
        self.assertIsNone(e.installed)
        self.assertEqual(len(e.leases), 0)

    def test_mixed_bind_skin_texture_never_published(self):
        e = Editor(example_body())
        key = e.start_job('current')
        products = dict.fromkeys(('skin', 'bind', 'texture'), key)
        products['bind'] = (41,) + key[1:]
        self.assertEqual(e.finish_job('current', key, products), 'Failed')
        self.assertIsNone(e.installed)
        self.assertEqual(e.compile_error, 'MixedArtifactVersions')

    def test_compile_failure_preserves_recipe_and_retry_installs(self):
        e = Editor(example_body())
        before = e.parts, e.balance, e.revision
        key = e.start_job('failed')
        self.assertEqual(e.finish_job('failed', key, {}, 'TessellationFailed'), 'Failed')
        self.assertEqual((e.parts, e.balance, e.revision), before)
        retry = e.start_job('retry')
        self.assertEqual(e.finish_job('retry', retry, dict.fromkeys(('skin', 'bind', 'texture'), retry)), 'Installed')
        self.assertEqual(e.installed, e.job_key())

    def test_visual_lod_work_units_are_separate_from_budget(self):
        self.assertEqual(visual_cost('high'), {'ik': 1920, 'matrices': 2760, 'weighted_vertex_products': 1920000})
        self.assertEqual(visual_cost('mid'), {'ik': 640, 'matrices': 640, 'weighted_vertex_products': 720000})
        self.assertEqual(visual_cost('low'), {'ik': 160, 'matrices': 90, 'weighted_vertex_products': 108000})
        self.assertEqual(totals(example_body())[1:], (88, 46, 8000))

    def test_lod_switch_does_not_change_support_phase_or_hit_authority(self):
        for time in (.0, .25, .5, 1.1, 4.75):
            expected = frame(time, 'high')['authority']
            self.assertEqual(frame(time, 'mid')['authority'], expected)
            self.assertEqual(frame(time, 'low')['authority'], expected)
        self.assertTrue(frame(.25, 'low')['authority']['hit_event_due'])
        self.assertEqual(frame(.25, 'low')['authority']['feet'], 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
