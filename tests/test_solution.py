"""Synthetic evidence tests: these are not copies of the practice answer key."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'submission'))
from solution import build


def page(rate='6.11%',url='https://example.org/personal/loans/auto-motorcycle-loans',extra=''):
    return Obj(url=url,title='Auto loans',markdown=f'''# Auto loans
| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2024-27 Model Year | 60 Months | {rate} |
{extra}
''',fetched_at='2026-01-01')


def snapshot(day,*pages):
    return Obj(snapshot_id='snapshot-'+day,taken_on=day,pages=list(pages))


class TemporalKnowledgeTests(unittest.TestCase):
    def setUp(self):self.ks=build()
    def test_input_mutation_and_as_of(self):
        self.ks.ingest(snapshot('2026-01-01',page('6.11%')))
        self.ks.ingest(snapshot('2026-03-01',page('7.22%')))
        q='APR for 60-month auto loan on 2025 vehicle'
        self.assertIn('7.22%',self.ks.answer(q).text)
        self.assertIn('6.11%',self.ks.answer(q,'2026-02-28').text)
        self.assertNotIn('7.22%',self.ks.answer(q,'2026-02-28').text)
        self.assertEqual(self.ks.answer(q,'2026-02-28').sources[0].snapshot_id,'snapshot-2026-01-01')
    def test_before_first_snapshot(self):
        self.ks.ingest(snapshot('2026-01-01',page()))
        self.assertFalse(self.ks.answer('auto rate','2025-01-01').confident)
    def test_full_snapshot_removal(self):
        self.ks.ingest(snapshot('2026-01-01',page()))
        self.ks.ingest(snapshot('2026-03-01'))
        self.assertFalse(self.ks.answer('60-month auto rate').confident)
    def test_wrong_year_and_term_abstain(self):
        self.ks.ingest(snapshot('2026-01-01',page()))
        self.assertFalse(self.ks.answer('60-month auto rate for 2018 vehicle').confident)
        self.assertFalse(self.ks.answer('84-month auto rate for 2025 vehicle').confident)
    def test_source_priority_and_conflict(self):
        self.ks.ingest(snapshot('2026-01-01',page('6.11%'),page('5.22%','https://example.org/calculators/auto')))
        a=self.ks.answer('60-month auto APR for 2025 vehicle')
        self.assertIn('6.11%',a.text);self.assertNotIn('5.22%',a.text)
        self.assertIsNotNone(a.conflict_note)
        conflicts=self.ks.conflicts()
        self.assertEqual(len(conflicts),1)
        self.assertEqual(conflicts[0].resolution,'6.11%')
    def test_tiers_not_conflicts(self):
        self.ks.ingest(snapshot('2026-01-01',page(extra='| 2021-23 Model Year | 60 Months | 8.77% |')))
        self.assertEqual(self.ks.conflicts(),[])
        self.assertIn('8.77%',self.ks.answer('60-month auto APR for 2022 vehicle').text)
    def test_normal_change_not_conflict(self):
        self.ks.ingest(snapshot('2026-01-01',page('6.11%')))
        self.ks.ingest(snapshot('2026-03-01',page('7.22%')))
        self.assertEqual(self.ks.conflicts(),[])
    def test_unresolved_conflict(self):
        self.ks.ingest(snapshot('2026-01-01',page('6.11%'),page('7.22%')))
        self.assertFalse(self.ks.answer('60-month auto APR').confident)
        self.assertIsNone(self.ks.conflicts()[0].resolution)
    def test_apr_apy_separate(self):
        p=Obj(url='https://example.org/personal/savings-account',title='Savings',markdown='''Certificates

| Certificate | Dividend Rate | Annual Percentage Yield (APY) |
| --- | --- | --- |
| 17 Month Fixed Certificate Special | 3.11% | 3.22% |
''')
        self.ks.ingest(snapshot('2026-01-01',p))
        a=self.ks.answer('17-month certificate APY')
        self.assertIn('APY 3.22%',a.text)
        self.assertIn('Dividend rate 3.11%',a.text)
        self.assertEqual(self.ks.conflicts(),[])
    def test_equivalent_terms(self):
        self.ks.ingest(snapshot('2026-01-01',page()))
        self.assertEqual(self.ks.answer('5-year car loan APR for 2025').text,self.ks.answer('60-month auto APR for 2025').text)
    def test_future_effective_rate_not_used(self):
        p=page();p.markdown+='\nRates are effective as of 03/01/2026.'
        self.ks.ingest(snapshot('2026-01-01',p))
        self.assertFalse(self.ks.answer('60-month auto APR').confident)
    def test_repeat_and_ingest_order(self):
        self.ks.ingest(snapshot('2026-03-01',page('7.22%')))
        self.ks.ingest(snapshot('2026-01-01',page('6.11%')))
        a=self.ks.answer('60-month auto APR')
        self.assertIn('7.22%',a.text)
        self.assertEqual(a,self.ks.answer('60-month auto APR'))
    def test_invalid_date(self):
        self.ks.ingest(snapshot('2026-01-01',page()))
        self.assertFalse(self.ks.answer('auto rate','garbage').confident)
    def test_explicit_question_date(self):
        self.ks.ingest(snapshot('2026-01-01',page('6.11%')))
        self.ks.ingest(snapshot('2026-03-01',page('7.22%')))
        self.assertIn('6.11%',self.ks.answer('60-month auto APR as of January 2026').text)

    def test_numeric_format_not_conflict(self):
        self.ks.ingest(snapshot('2026-01-01',page('6.10%'),page('6.1%','https://example.org/calculators/auto')))
        self.assertEqual(self.ks.conflicts(),[])
    def test_card_identity_in_header(self):
        p=Obj(url='https://example.org/business/credit-cards',title='Cards',markdown='| Business Platinum Visa | Annual Percentage Rate (APR) |\n| --- | --- |\n| Variable Interest Rate | 11.5% |\n\n| Business Rewards Visa | Annual Percentage Rate (APR) |\n| --- | --- |\n| Variable Interest Rate | 14.5% |\n')
        self.ks.ingest(snapshot('2026-01-01',p))
        self.assertEqual(self.ks.conflicts(),[])
        answer=self.ks.answer('business platinum visa APR')
        self.assertIn('11.5%',answer.text)
        self.assertNotIn('14.5%',answer.text)

if __name__=='__main__': unittest.main()
