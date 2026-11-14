"""Fail publication on private records, unknown places or unsafe small groups."""
import json
from pathlib import Path
from normalization import SAFE_LOCATIONS
from publication import MIN_PUBLIC_SAMPLE

FORBIDDEN = {'datetime','booking_code','phone','email','raw_service','fare_components',
             'transactions','latitude','longitude','coordinates','lat','lng','raw_text','receipt'}
# 'transactions' is permitted only as a numeric source/provider summary count.
def validate(data):
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in FORBIDDEN and not (key=='transactions' and isinstance(item,int)):
                    raise ValueError('Private field in public analytics')
                if key in ('origin','destination','restaurant') and item not in SAFE_LOCATIONS:
                    raise ValueError('Unapproved public location')
                if key=='stops' and (not isinstance(item,list) or any(x not in SAFE_LOCATIONS for x in item)):
                    raise ValueError('Unapproved public stop')
                visit(item)
            if 'count' in value and any(k in value for k in ('median','average','total_spend')):
                if value['count'] < MIN_PUBLIC_SAMPLE:
                    raise ValueError('Small public group')
            if 'min' in value or 'max' in value:
                raise ValueError('Individual fare extremes must not be public')
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(data)
    for month in data.get('monthly', []):
        if month.get('count', 0) < MIN_PUBLIC_SAMPLE:
            raise ValueError('Monthly sample count missing or too small')
        for component in ('Grab rides','Gojek rides','GrabFood'):
            if component in month and month.get('component_counts', {}).get(component, 0) < MIN_PUBLIC_SAMPLE:
                raise ValueError('Unsafe monthly component')
    routes=data.get('routes',[])
    if len({r['key'] for r in routes}) != len(routes):
        raise ValueError('Duplicate route identities')
    for route in routes:
        if route['overall']['count'] < MIN_PUBLIC_SAMPLE:
            raise ValueError('Small public route')
    return True

def main():
    data=json.loads(Path('docs/data/analytics.json').read_text())
    validate(data)
    distances=json.loads(Path('config/route_distances.json').read_text())
    if set(distances['routes']) - {r['key'] for r in data['routes']}:
        raise ValueError('Orphaned distance routes can disclose withheld journeys')
    for route in distances['routes'].values():
        if route['origin'] not in SAFE_LOCATIONS or route['destination'] not in SAFE_LOCATIONS:
            raise ValueError('Unapproved distance location')
    for path in Path('docs').rglob('*'):
        if path.suffix.lower() in {'.pdf','.csv','.zip','.bak'} or path.name in {'transactions.json','private_aliases.json'}:
            raise ValueError('Private or unreviewed file in site output')
    print('Public artifact checks passed; no raw records or small fare groups.')

if __name__=='__main__':main()
