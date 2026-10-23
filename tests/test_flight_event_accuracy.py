from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sixd import powered_flight as flight
from test_powered_flight import parameters


class FlightEventAccuracyTests(unittest.TestCase):
    def test_fractional_cutoff_is_exact_on_every_grid_including_zero_coast(self):
        for n in (13,15,31):
            for coast in (0,2):
                with self.subTest(steps=n,coast=coast):
                    p=parameters(initial_mass=987.3,dry_mass=641.7,thrust=19237,steps=n,coast_duration=coast)
                    metrics,a=flight.evaluate(p)
                    burn=metrics['burn_duration']['value']
                    for rows in (a['samples'],a['refinement']['coarse_samples'],a['refinement']['middle_samples']):
                        self.assertTrue(all(x['time_s'] <= y['time_s'] for x,y in zip(rows,rows[1:])))
                        before=next(r for r in rows if r['event']=='before_cutoff')
                        self.assertEqual(before['time_s'],burn)
                        self.assertEqual(before['mass_kg'],p['dry_mass'])
                        self.assertEqual(rows[-1]['time_s'],burn+coast)
                        if coast:
                            after=next(r for r in rows if r['event']=='after_cutoff')
                            for key in ('time_s','mass_kg','altitude_m','velocity_m_s'):
                                self.assertEqual(before[key],after[key])
                            self.assertEqual(after['thrust_n'],0)
                    with patch.object(flight,'_integrate',side_effect=AssertionError('No history integration')):
                        self.assertTrue(flight.validate_artifact(a,metrics,p,a['source_fingerprint']))

    def test_later_source_edit_cannot_relabel_loaded_solver(self):
        expected=flight._LOADED_SOURCE_FINGERPRINT
        with patch.object(Path,'read_bytes',return_value=b'later unexecuted source'):
            _,a=flight.evaluate(parameters())
        self.assertEqual(a['source_fingerprint'],expected)


if __name__=='__main__':unittest.main()
