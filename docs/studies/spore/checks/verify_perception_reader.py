"""Validate selected registry identities and observation separation, not runtime AI."""
import json
from pathlib import Path
import unittest
from read_selected_ability_properties import FormatError, fnv
from read_selected_perception_properties import names_from_registry


class PerceptionReaderChecks(unittest.TestCase):
    def test_explicit_ids_and_bare_fnv_and_scenario_exclusion(self):
        names=names_from_registry({'selected_declarations':[
            {'text':'creatureUntargetDistance 0x01C2301B'},
            {'text':'creatureFleeRememberTime'},
            {'text':'creatureScenarioFightThreatRating'}]})
        self.assertEqual(names[0x01C2301B],'creatureUntargetDistance')
        self.assertEqual(names[fnv('creatureFleeRememberTime')],'creatureFleeRememberTime')
        self.assertNotIn(fnv('creatureScenarioFightThreatRating'),names)

    def test_conflicting_names_reported(self):
        with self.assertRaises(FormatError):
            names_from_registry({'selected_declarations':[
                {'text':'creatureFirst 0x111'}, {'text':'creatureOther 0x111'}]})

    def test_recorded_variants_parents_and_absence_remain_separate(self):
        p=Path(__file__).resolve().parent.parent/'evidence/local-selected-perception-properties.json'
        d=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(len(d['records']),8)
        self.assertEqual(len(d['packages']),2)
        for package in ('Spore_Game.package','PatchData.package'):
            rows={r['key']['group']:r for r in d['records'] if r['package']==package}
            self.assertEqual(set(rows),{'0x00000000','0x02ae0c7e','0xad56080c','0xf71fa311'})
            main=rows['0xad56080c']
            self.assertEqual(main['property_count'],249)
            self.assertEqual(main['selected_properties']['creatureFleeRememberTime']['values'],[90])
            self.assertEqual(main['selected_properties']['creatureUntargetDistance']['values'],[17.5])
            self.assertIn('creatureSightRadius',main['not_written_here'])
            self.assertIn('creatureHungerDrain',main['not_written_here'])
            variant=rows['0xf71fa311']['selected_properties']
            self.assertEqual(variant['creatureMaxPerceptionRadius']['values'],[30])
            self.assertEqual(variant['parent']['values'][0]['group'],'0xad56080c')

    def test_selected_ai_values_equal_between_packages_not_effective_load_order(self):
        p=Path(__file__).resolve().parent.parent/'evidence/local-selected-perception-properties.json'
        d=json.loads(p.read_text(encoding='utf-8'))
        rows={(r['package'],r['key']['group']):r for r in d['records']}
        for g in ('0x00000000','0x02ae0c7e','0xad56080c','0xf71fa311'):
            self.assertEqual(rows[('Spore_Game.package',g)]['selected_properties'],
                             rows[('PatchData.package',g)]['selected_properties'])
        self.assertIn('unknown',d['package_load_order'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
