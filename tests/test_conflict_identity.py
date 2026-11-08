"""Regressions for audience identity and evidence-specific conflict explanations."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'submission'))
from solution import build


def savings(url, rate, product='Share Savings', effective=''):
    markdown = f'''# Savings

| Account Type | Balance Tier | Dividend Rate | Annual Percentage Yield (APY) |
| --- | --- | --- | --- |
| {product} | $10,000 - $24,999.99 | {rate} | {rate} |
'''
    if effective:
        markdown += '\nRates are effective as of ' + effective + '.'
    return Obj(url=url, title='Savings', markdown=markdown)


def snap(day, *pages):
    return Obj(taken_on=day, snapshot_id='snapshot-' + day, pages=list(pages))


class ConflictIdentityTests(unittest.TestCase):
    def test_business_legacy_and_nested_paths_stay_separate_from_personal(self):
        for business_url in ('https://example.org/business-rates',
                             'https://example.org/business/savings-accounts'):
            with self.subTest(url=business_url):
                system = build()
                system.ingest(snap('2026-08-01',
                    savings(business_url, '0.29%'),
                    savings('https://example.org/personal/savings-account', '0.17%')))
                self.assertEqual(system.conflicts(), [])
                personal = system.answer('Share Savings dividend rate with $10,000')
                business = system.answer('Business Share Savings dividend rate with $10,000')
                self.assertIn('0.17%', personal.text)
                self.assertNotIn('0.29%', personal.text)
                self.assertIn('0.29%', business.text)
                self.assertNotIn('0.17%', business.text)

    def test_business_only_evidence_cannot_answer_personal_query(self):
        system = build()
        system.ingest(snap('2026-08-01', savings('https://example.org/business-rates', '0.29%')))
        self.assertFalse(system.answer('Personal Share Savings rate').confident)

    def test_unknown_audience_not_assumed_personal(self):
        system = build()
        system.ingest(snap('2026-08-01',
            savings('https://example.org/rates', '0.29%'),
            savings('https://example.org/personal/savings-account', '0.17%')))
        self.assertEqual(system.conflicts(), [])
        self.assertIn('0.17%', system.answer('Share Savings dividend rate').text)

    def test_same_business_product_still_detects_conflict(self):
        system = build()
        preferred = 'https://example.org/business/savings-accounts'
        other = 'https://example.org/business-rates'
        system.ingest(snap('2026-08-01', savings(preferred, '0.17%'), savings(other, '0.29%')))
        conflicts = system.conflicts()
        self.assertEqual(len(conflicts), 2)  # dividend rate and APY
        for conflict in conflicts:
            self.assertEqual(conflict.resolution, '0.17%')
            self.assertIn('business', conflict.topic)
            self.assertIn(preferred, conflict.reason)
            self.assertIn(other, conflict.reason)
            self.assertIn('higher authority', conflict.reason)
            self.assertNotIn('selected effective date', conflict.reason)

    def test_explicit_product_audience_on_general_page(self):
        system = build()
        system.ingest(snap('2026-08-01',
            savings('https://example.org/rates', '0.29%', product='Business Share Savings'),
            savings('https://example.org/business/savings-accounts', '0.17%', product='Business Share Savings')))
        self.assertEqual(len(system.conflicts()), 2)
        self.assertTrue(all(c.resolution == '0.17%' for c in system.conflicts()))

    def test_effective_date_reason_reports_actual_dates(self):
        system = build()
        newer = 'https://example.org/personal/savings-current'
        older = 'https://example.org/personal/savings-old'
        system.ingest(snap('2026-08-01',
            savings(newer, '0.17%', effective='07/01/2026'),
            savings(older, '0.29%', effective='06/01/2026')))
        for conflict in system.conflicts():
            self.assertEqual(conflict.resolution, '0.17%')
            self.assertIn('2026-07-01', conflict.reason)
            self.assertIn('2026-06-01', conflict.reason)
            self.assertIn('effective as of', conflict.sources[0].quote)

    def test_equal_authority_disagreement_stays_unresolved(self):
        system = build()
        system.ingest(snap('2026-08-01',
            savings('https://example.org/personal/savings-a', '0.17%'),
            savings('https://example.org/personal/savings-b', '0.29%')))
        self.assertFalse(system.answer('Share Savings rate').confident)
        for conflict in system.conflicts():
            self.assertIsNone(conflict.resolution)
            self.assertIn('Unresolved', conflict.reason)
            self.assertIn('savings-a', conflict.reason)
            self.assertIn('savings-b', conflict.reason)

    def test_historical_conflict_label(self):
        system = build()
        system.ingest(snap('2026-07-01',
            savings('https://example.org/business/savings', '0.17%'),
            savings('https://example.org/business-rates', '0.29%')))
        system.ingest(snap('2026-08-01', savings('https://example.org/business/savings', '0.17%')))
        self.assertTrue(all('Historical conflict; last observed 2026-07-01' in c.reason
                            for c in system.conflicts()))

    def test_future_effective_claim_not_reported_as_current_conflict(self):
        system = build()
        system.ingest(snap('2026-08-01',
            savings('https://example.org/personal/savings-a', '0.17%'),
            savings('https://example.org/personal/savings-b', '0.29%', effective='09/01/2026')))
        self.assertEqual(system.conflicts(), [])


if __name__ == '__main__':
    unittest.main()
