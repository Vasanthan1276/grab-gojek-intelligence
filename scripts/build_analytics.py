\
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import numpy as np


def _stats(vals):
    vals=np.array(vals,dtype=float)
    if len(vals)==0:return None
    return {'count':len(vals),'average':round(float(vals.mean()),2),'median':round(float(np.median(vals)),2),
            'min':round(float(vals.min()),2),'max':round(float(vals.max()),2),
            'p10':round(float(np.percentile(vals,10)),2),'p25':round(float(np.percentile(vals,25)),2),
            'p75':round(float(np.percentile(vals,75)),2),'p90':round(float(np.percentile(vals,90)),2)}

def _bucket(h):
    return ('Overnight (00-05)' if h<5 else 'Early morning (05-07)' if h<7 else 'Morning peak (07-10)' if h<10
            else 'Midday (10-14)' if h<14 else 'Afternoon (14-17)' if h<17 else 'Evening (17-21)' if h<21 else 'Night (21-24)')

def build(transactions):
    sgd=[x for x in transactions if x['currency']=='SGD']; rides=[x for x in sgd if x['category']=='ride']; foods=[x for x in sgd if x['category']=='food']
    groups=defaultdict(list)
    for x in rides:groups[(x['origin'],x['destination'])].append(x)
    routes=[]
    for (o,d),rows in groups.items():
        providers={}
        for p in ('Grab','Gojek'):
            vals=[x['amount'] for x in rows if x['provider']==p]
            if vals:providers[p]=_stats(vals)
        buckets={}
        for b in set(_bucket(x['hour']) for x in rows):
            buckets[b]=_stats([x['amount'] for x in rows if _bucket(x['hour'])==b])
        routes.append({'key':f'{o}__{d}','origin':o,'destination':d,'overall':_stats([x['amount'] for x in rows]),'providers':providers,'time_buckets':buckets})
    routes.sort(key=lambda x:x['overall']['count'],reverse=True)
    return {'summary':{'total_transactions':len(transactions),'total_spend_sgd':round(sum(x['amount'] for x in sgd),2)},'routes':routes}
