"""All statement examples are fictional; no personal receipt data is used."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from import_grab_statement import HEADER, parse_statement
from refresh_history import merge_records, require_historical_coverage
from normalization import normalize_location


def fixture():
    return [{'text': '2026-08-01 - 2026-08-31 Total Transactions: 2 Amount: SGD 30.50',
             'tables': [[HEADER, ['02 Aug 2026,\n09:15AM', 'A-FICTIONAL-1', 'HOME', 'OFFICE',
                                 'Standard | Car or taxi', 'SGD', '10.00'],
                         ['03 Aug 2026,\n12:00AM', 'A-FICTIONAL-2', 'OFFICE', 'HOME',
                          'Standard | Metered taxi only', 'SGD', '20.50']]]}]


class StatementTests(unittest.TestCase):
    def test_category_change_cannot_duplicate_the_same_payment(self):
        old = parse_statement(fixture())[:1]
        new = copy.deepcopy(old)
        new[0]['category'] = 'food'
        for with_reference in (True, False):
            if not with_reference:
                old[0].pop('booking_code'); new[0].pop('booking_code')
            with self.assertRaises(ValueError): merge_records(old, new)

    def test_same_minute_distinct_booking_can_be_food_and_ride(self):
        old = parse_statement(fixture())[:1]
        new = copy.deepcopy(old)
        new[0].update(category='food', booking_code='A-FICTIONAL-FOOD')
        self.assertEqual(len(merge_records(old, new)[0]), 2)

    def test_booking_reference_cannot_reappear_with_changed_timestamp(self):
        old = parse_statement(fixture())[:1]
        new = copy.deepcopy(old)
        new[0]['datetime'] = '2026-08-02T09:16'
        with self.assertRaises(ValueError): merge_records(old, new)

    def test_native_food_does_not_enter_ride_categories(self):
        pages = fixture(); pages[0]['tables'][0][1][4] = 'GrabFood'
        row = parse_statement(pages)[0]
        self.assertEqual((row['category'], row['pricing_type']), ('food', 'Food'))

    def test_more_new_rows_cannot_hide_missing_older_history(self):
        rows = parse_statement(fixture())
        old = {'source_summary': {'Grab': {'period': '2026-08-01 to 2026-08-31', 'transactions': 2}},
               'providers': {'Grab': {'spend_sgd': 30.50}}}
        self.assertTrue(require_historical_coverage(rows, old)[0]['matches'])
        newer = [dict(rows[1], date='2026-09-01') for _ in range(10)]
        with self.assertRaises(ValueError): require_historical_coverage(rows[:1] + newer, old)

    def test_same_count_with_wrong_old_total_is_rejected(self):
        rows = parse_statement(fixture()); rows[0]['amount'] += 1
        old = {'source_summary': {'Grab': {'period': '2026-08-01 to 2026-08-31', 'transactions': 2}},
               'providers': {'Grab': {'spend_sgd': 30.50}}}
        with self.assertRaises(ValueError): require_historical_coverage(rows, old)

    def test_first_import_and_unknown_prior_coverage(self):
        self.assertEqual(require_historical_coverage(parse_statement(fixture()), {}), [])
        with self.assertRaises(ValueError): require_historical_coverage([], {'summary': {'total_transactions': 20}})

    def test_recovered_alias_matches_exactly(self):
        aliases = [{'alias':'HOME', 'equals':['Fictional Residence']}]
        self.assertEqual(normalize_location('fictional residence', aliases), 'HOME')
        self.assertNotEqual(normalize_location('Fictional Residence Annex', aliases), 'HOME')

    def test_duplicate_sources_are_retained_without_mutating_inputs(self):
        old = parse_statement(fixture(), source_sha256='old')
        new = parse_statement(fixture(), source_sha256='new')
        merged, duplicate_count, added = merge_records(old, new)
        self.assertEqual((duplicate_count, added), (2, 0))
        self.assertEqual(len(merged[0]['source_references']), 2)
        self.assertEqual(len(old[0]['source_references']), 1)
        self.assertEqual(merge_records(merged, new)[0], merged)

    def test_distinct_booking_codes_at_same_minute_need_review(self):
        old = parse_statement(fixture()); new = copy.deepcopy(old)
        new[0]['booking_code'] = 'A-DIFFERENT-BOOKING'
        with self.assertRaises(ValueError): merge_records(old, new)

    def test_exact_totals_categories_direction_and_midnight(self):
        rows = parse_statement(fixture(), source_sha256='synthetic')
        self.assertEqual([r['pricing_type'] for r in rows], ['Fixed', 'Metered'])
        self.assertEqual(rows[1]['hour'], 0)
        self.assertEqual((rows[1]['origin'], rows[1]['destination']), ('OFFICE', 'HOME'))
        self.assertEqual(rows[0]['source_references'][0]['table_row'], 2)

    def test_count_and_total_must_reconcile(self):
        for old, new in [('2 Amount', '3 Amount'), ('30.50', '30.51')]:
            pages = fixture(); pages[0]['text'] = pages[0]['text'].replace(old, new)
            with self.assertRaises(ValueError): parse_statement(pages)

    def test_no_silent_skipping_of_bad_rows(self):
        for col, value in [(0, 'bad date'), (2, ''), (6, '-10.00'), (6, '10.OO'), (5, 'USD')]:
            pages = fixture(); pages[0]['tables'][0][1][col] = value
            with self.assertRaises(ValueError): parse_statement(pages)

    def test_duplicate_booking_is_rejected(self):
        pages = fixture(); pages[0]['tables'][0][2][1] = 'A-FICTIONAL-1'
        with self.assertRaises(ValueError): parse_statement(pages)

    def test_wrapped_booking_reference_is_retained(self):
        pages = fixture(); pages[0]['tables'][0][1][1] = 'A-FICTIONAL-\n1'
        self.assertEqual(parse_statement(pages)[0]['booking_code'], 'A-FICTIONAL-1')

    def test_dates_must_fit_statement_period(self):
        pages = fixture(); pages[0]['tables'][0][1][0] = '02 Sep 2026, 09:15AM'
        with self.assertRaises(ValueError): parse_statement(pages)

    def test_multistop_marker_requires_review(self):
        pages = fixture(); pages[0]['tables'][0][1][2] = 'HOME via Fictional Stop'
        self.assertEqual(parse_statement(pages)[0]['route_status'], 'needs_review')

    def test_reordered_or_missing_header_is_rejected(self):
        pages = copy.deepcopy(fixture()); pages[0]['tables'][0][0][0] = 'Other'
        with self.assertRaises(ValueError): parse_statement(pages)

    def test_blank_footer_is_ignored_but_partial_row_is_rejected(self):
        pages = fixture(); pages[0]['tables'][0].append([''] * 7)
        self.assertEqual(len(parse_statement(pages)), 2)
        pages[0]['tables'][0][-1][2] = 'private text should never appear in errors'
        with self.assertRaises(ValueError) as error: parse_statement(pages)
        self.assertNotIn('private text', str(error.exception))
