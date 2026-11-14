import copy
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from normalization import normalize_location
from journey import journey, pricing_type, possible_multistop
from publication import public_analytics
from build_analytics import build, apply_distance_metrics, _stats
from refresh_history import normalize_record, merge_records
from import_grab_pdf import _service, import_grab_pdf
from import_gojek_pdf import parse_row, import_gojek_pdf
from build_route_distances import response_json, current_distance_record, round_distance
from validate_public import validate


def rows(n=10, **changes):
    out=[]
    for i in range(n):
        row={'provider':'Grab','category':'ride','service':'JustGrab','currency':'SGD',
             'origin':'HOME','destination':'OFFICE','amount':10+i,
             'date':f'2026-01-{i+1:02d}','datetime':f'2026-01-{i+1:02d}T08:00',
             'hour':8,'weekday':'Monday'}
        row.update(changes);out.append(row)
    return out

class PipelineTests(unittest.TestCase):
    def test_statistics_known_values(self):
        s=_stats([10,20,30,40,50]);self.assertEqual(s['median'],30);self.assertEqual(s['p25'],20);self.assertEqual(s['average'],30)
    def test_unknown_location_is_private(self):
        for value in ['Apartment Z fictional road','Post office','JEMSTONE','123 Fictional Avenue']:
            self.assertTrue(normalize_location(value).startswith('PRIVATE_'))
    def test_explicit_alias_and_boundaries(self):
        aliases=[{'alias':'V_PLACE','contains':['FICTIONAL STOP Z']}]
        self.assertEqual(normalize_location('Fictional Stop Z lobby',aliases),'V_PLACE')
        self.assertEqual(normalize_location('JEM mall'),'JEM')
        self.assertNotEqual(normalize_location('JEMSTONE'),'JEM')
    def test_unsafe_alias_rejected(self):
        result=normalize_location('fictional xyz',[{'alias':'Fictional private street','contains':['xyz']}])
        self.assertTrue(result.startswith('PRIVATE_'))
    def test_pricing_categories(self):
        for raw,kind in [('Standard | Metered taxi only','Metered'),('JustGrab','Fixed'),('Premium','Premium'),('', 'Unknown'),('Other service','Unknown')]:
            self.assertEqual(_service(raw)[2],kind)
        self.assertEqual(pricing_type(''), 'Unknown')
    def test_direction_and_multistop_not_collapsed(self):
        tx=rows(5,stops=['HOME','OFFICE'])+rows(5,origin='OFFICE',destination='HOME',stops=['OFFICE','HOME'])+rows(5,stops=['HOME','V_PLACE','OFFICE'])+rows(5)
        data=build(tx)
        self.assertEqual(len(data['routes']),4)
        self.assertEqual(len({r['key'] for r in data['routes']}),4)
        multi=next(r for r in data['routes'] if r['journey_type']=='multi_stop')
        self.assertEqual(multi['stops'],['HOME','V_PLACE','OFFICE'])
    def test_unknown_stops_not_direct(self):
        self.assertEqual(journey(rows(1)[0])[1],'stop_coverage_unknown')
    def test_ambiguous_multistop_quarantined(self):
        self.assertTrue(possible_multistop('HOME via V_PLACE'))
        self.assertEqual(build(rows(10,route_status='needs_review'))['routes'],[])
        self.assertIsNone(journey(rows(1,stops=['V_PLACE','OFFICE'])[0]))
    def test_private_intermediate_stop_excluded(self):
        self.assertFalse(build(rows(6,stops=['HOME','PRIVATE_FAKE','OFFICE']))['routes'])
    def test_zero_fare_retained_not_missing(self):
        data=build(rows(5,amount=0));self.assertEqual(data['routes'][0]['overall']['median'],0)
    def test_missing_nan_infinite_negative_amount_rejected(self):
        for bad in [None,float('nan'),float('inf'),-1]:
            with self.assertRaises(ValueError):build(rows(5,amount=bad))
    def test_currency_separation(self):
        data=build(rows(5)+rows(5,currency='MYR',amount=900))
        self.assertEqual(data['summary']['ride_spend_sgd'],60)
        self.assertEqual(data['routes'][0]['overall']['count'],5)
    def test_route_and_group_dates(self):
        r=build(rows(5))['routes'][0]
        self.assertEqual(r['providers']['Grab']['date_range'],{'start':'2026-01-01','end':'2026-01-05'})
    def test_small_groups_and_extremes_suppressed(self):
        data=build(rows(3)+rows(5,provider='Gojek',service='Gojek'))
        r=data['routes'][0]
        self.assertNotIn('Grab',r['providers']);self.assertNotIn('min',r['overall']);self.assertNotIn('max',r['overall'])
        self.assertEqual(build(rows(1),trusted_route_keys={'HOME__OFFICE'})['routes'],[])
    def test_distance_division_and_missing_are_safe(self):
        data=build(rows(5));history=data['generated_on']
        apply_distance_metrics(data,{'routes':{'HOME__OFFICE':{'distance_km':10,'source':'Fixture','calculated_on':'2026-01-01'}}})
        self.assertEqual(data['routes'][0]['cost_per_km']['overall']['median'],1.2)
        self.assertEqual(data['generated_on'],history)
        apply_distance_metrics(data,{'routes':{}})
        self.assertNotIn('distance',data['routes'][0]);self.assertEqual(data['distance_analysis']['routes_with_distance'],0)
    def test_invalid_distances(self):
        for bad in [0,-1,None,'bad',float('nan'),float('inf')]:
            data=build(rows(5));apply_distance_metrics(data,{'routes':{'HOME__OFFICE':{'distance_km':bad}}})
            self.assertNotIn('distance',data['routes'][0])
    def test_multistop_distance_requires_ordered_stop_match(self):
        data=build(rows(5,stops=['HOME','V_PLACE','OFFICE']));key=data['routes'][0]['key']
        apply_distance_metrics(data,{'routes':{key:{'distance_km':10}}})
        self.assertNotIn('distance',data['routes'][0])
        apply_distance_metrics(data,{'routes':{key:{'distance_km':20,'stops':['HOME','V_PLACE','OFFICE']}}})
        self.assertEqual(data['routes'][0]['distance']['distance_km'],20)
    def test_duplicate_and_conflicting_imports(self):
        old=rows(2);merged,duplicates,added=merge_records(old,copy.deepcopy(old))
        self.assertEqual((len(merged),duplicates,added),(2,2,0))
        for field,value in [('amount',70),('destination','V_PLACE')]:
            changed=copy.deepcopy(old);changed[0][field]=value
            with self.assertRaises(ValueError):merge_records(old,changed)
        changed=copy.deepcopy(old);changed[0]['currency']='UNKNOWN'
        with self.assertRaises(ValueError):merge_records(old,changed)
        old[0]['pricing_type']='Fixed';changed=copy.deepcopy(old);changed[0]['pricing_type']='Metered'
        with self.assertRaises(ValueError):merge_records(old,changed)
    def test_normalize_does_not_invent_amount_currency_or_pricing(self):
        r=rows(1)[0];del r['currency'];r['service']=''
        n=normalize_record(r,[]);self.assertEqual(n['currency'],'UNKNOWN');self.assertEqual(n['pricing_type'],'Unknown')
        r['amount']=None
        with self.assertRaises(ValueError):normalize_record(r,[])
    def test_gojek_amount_and_multistop_parser(self):
        r=['01/01/2026 08:00:00 AM','','','HOME','OFFICE\nStop 2: V_PLACE','','SGD 1,234.50']
        result=parse_row(r);self.assertEqual(result['amount'],1234.5);self.assertEqual(result['route_status'],'needs_review')
        r[6]='25.00';self.assertEqual(parse_row(r)['currency'],'UNKNOWN')
        for value in ['-3.50','SGD unknown','SGD 2.50 + 3.00']:
            r[6]=value
            with self.assertRaises(ValueError):parse_row(r)
    def test_gojek_headers_and_bad_rows(self):
        pdf=Mock();pdf.pages=[Mock(),Mock()]
        valid=['01/01/2026 08:00:00 AM','','','HOME','OFFICE','','SGD 25.00']
        for page in pdf.pages:page.extract_table.return_value=[['Date'],valid]
        with patch('import_gojek_pdf.pdfplumber.open') as opener:
            opener.return_value.__enter__.return_value=pdf
            self.assertEqual(len(import_gojek_pdf('fictional.pdf')),2)
            pdf.pages[1].extract_table.return_value=[['malformed']]
            with self.assertRaisesRegex(ValueError,'page 2, row 1'):import_gojek_pdf('fictional.pdf')
    def test_grab_row_alignment_stops_on_mismatch(self):
        with patch('import_grab_pdf._render',return_value=[Mock()]),patch('import_grab_pdf._date_rows',return_value=[('date',10)]),patch('import_grab_pdf._amounts',return_value=[]):
            with self.assertRaisesRegex(RuntimeError,'OCR row mismatch'):import_grab_pdf('fixture.pdf')
    def test_no_network_error_body_leaks(self):
        response=Mock(ok=False,status_code=403,text='SECRET LOCATION AND TOKEN')
        with self.assertRaises(RuntimeError) as caught:response_json(response,'Request')
        self.assertNotIn('SECRET',str(caught.exception));self.assertIn('403',str(caught.exception))
    def test_carried_forward_distance_keeps_original_date(self):
        r=current_distance_record({'HOME__OFFICE':{'distance_km':12,'calculated_on':'2026-01-01'}},{'key':'HOME__OFFICE','origin':'HOME','destination':'OFFICE','count':8})
        self.assertEqual(r['calculated_on'],'2026-01-01');self.assertEqual(r['status'],'carried_forward')
        self.assertEqual(round_distance(12.3),12.5)
        self.assertIsNone(current_distance_record({'HOME__OFFICE':{'distance_km':'invalid'}},{'key':'HOME__OFFICE'}))
    def test_legacy_monthly_counts_are_not_assumed(self):
        data=build(rows(6));data['monthly']=[{'month':'2026-01','total':100}]
        self.assertEqual(public_analytics(data)['monthly'],[])
    def test_small_monthly_components_are_not_zero(self):
        data=build(rows(6)+rows(1,category='food'))
        self.assertNotIn('GrabFood',data['monthly'][0])
        self.assertIn('Grab rides',data['monthly'][0])
        validate(data)
    def test_public_validator_rejects_private_fields(self):
        data=build(rows(6));data['routes'][0]['latitude']=1.23
        with self.assertRaises(ValueError):validate(data)
    def test_publication_idempotent(self):
        data=build(rows(6));self.assertEqual(public_analytics(data),data)

if __name__ == '__main__':unittest.main()
