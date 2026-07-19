\
from __future__ import annotations
import re, tempfile
from datetime import datetime
from pathlib import Path
import fitz
import pandas as pd
import pytesseract
from PIL import Image
from pytesseract import Output
from normalization import normalize_location

BASE_W, BASE_H = 1870, 2420

def _render(pdf_path):
    doc=fitz.open(pdf_path)
    images=[]
    zoom=220/72
    matrix=fitz.Matrix(zoom, zoom)
    for page in doc:
        pix=page.get_pixmap(matrix=matrix, alpha=False)
        images.append(Image.frombytes('RGB',[pix.width,pix.height],pix.samples))
    return images


def _data(image, psm=6):
    d=pytesseract.image_to_data(image, config=f'--psm {psm}', output_type=Output.DATAFRAME)
    return d[(d.conf >= 0) & d.text.notna()].copy()


def _date_rows(image, first_page):
    w,h=image.size; y0=int(h*(440/BASE_H if first_page else 55/BASE_H))
    crop=image.crop((int(w*115/BASE_W),y0,int(w*315/BASE_W),h)).resize((400,(h-y0)*2))
    d=_data(crop,6)
    lines=[]
    for _,g in d.groupby(['block_num','par_num','line_num']):
        g=g.sort_values('left'); text=' '.join(g.text.astype(str))
        lines.append((float(g.top.min()),float((g.top+g.height).max()),text))
    lines.sort()
    out=[]; i=0
    while i < len(lines)-1:
        date_text=lines[i][2].strip(); time_text=lines[i+1][2].strip()
        if re.match(r'\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}',date_text) and re.search(r'\d{1,2}:\d{2}(?:AM|PM)',time_text,re.I):
            dt=datetime.strptime(re.sub(r',$','',date_text)+' '+time_text.upper(),'%d %b %Y %I:%M%p')
            center=y0+((lines[i][0]+lines[i+1][1])/2)/2
            out.append((dt,center)); i+=2
        else: i+=1
    return out


def _amounts(image, first_page):
    w,h=image.size; y0=int(h*(440/BASE_H if first_page else 55/BASE_H))
    crop=image.crop((int(w*1655/BASE_W),y0,int(w*1795/BASE_W),h)).resize((420,(h-y0)*3))
    d=_data(crop,6); vals=[]
    for text in d.text.astype(str):
        m=re.search(r'\d+(?:\.\d+)?',text)
        if m: vals.append(float(m.group()))
    return vals


def _service(raw):
    u=str(raw).upper()
    if 'GRABFOOD' in u or 'GRABOOD' in u: return 'GrabFood','food'
    if 'METERED' in u: return 'Metered Taxi','ride'
    if 'JUSTGRAB' in u: return 'JustGrab','ride'
    if '4 SEATER' in u: return 'Standard 4-seater','ride'
    if 'PLUS' in u: return 'Standard Plus','ride'
    return 'Standard','ride'


def import_grab_pdf(pdf_path, aliases=None):
    records=[]
    for page_index,image in enumerate(_render(pdf_path)):
        first=page_index==0; drows=_date_rows(image,first); amounts=_amounts(image,first)
        if len(drows) != len(amounts):
            raise RuntimeError(f'OCR row mismatch on page {page_index+1}: {len(drows)} dates vs {len(amounts)} amounts')
        d=_data(image,6); d['yc']=d.top+d.height/2
        w,h=image.size
        centers=[c for _,c in drows]
        if len(centers)>1:
            bounds=[centers[0]-(centers[1]-centers[0])/2]+[(centers[i]+centers[i+1])/2 for i in range(len(centers)-1)]+[centers[-1]+(centers[-1]-centers[-2])/2]
        else: bounds=[0,h]
        cols={'pickup':(520,930),'dropoff':(930,1350),'service':(1350,1570),'currency':(1570,1665)}
        for i,(dt,center) in enumerate(drows):
            row=d[(d.yc>=bounds[i])&(d.yc<bounds[i+1])]; parsed={}
            for name,(a,b) in cols.items():
                a=int(w*a/BASE_W); b=int(w*b/BASE_W)
                words=row[(row.left>=a)&(row.left<b)].sort_values(['top','left'])
                parsed[name]=' '.join(words.text.astype(str))
            service,category=_service(parsed['service'])
            currency='MYR' if 'MYR' in parsed['currency'].upper() else 'SGD'
            dest=normalize_location(parsed['dropoff'],aliases)
            if category=='food' and dest not in {'HOME','OFFICE','V_PLACE'}:
                dest='OTHER_DELIVERY_LOCATION'
            records.append({
                'datetime':dt.isoformat(timespec='minutes'),'date':dt.date().isoformat(),
                'time':dt.strftime('%H:%M'),'hour':dt.hour,'weekday':dt.strftime('%A'),
                'provider':'Grab','category':category,'service':service,
                'origin':normalize_location(parsed['pickup'],aliases),'destination':dest,
                'amount':round(amounts[i],2),'currency':currency
            })
    return records
