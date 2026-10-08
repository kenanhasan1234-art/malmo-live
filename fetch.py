#!/usr/bin/env python3
"""Public listing collector. Run only when website access/terms permit it.
Fails closed: preserves prior verified feed if sources are inaccessible.
"""
import json, re, os, sys, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'feed.json'
STATE=ROOT/'collector'/'state.json'
FB='https://www.fastighetsbyran.com/sv/sverige/till-salu?kon=382'
HN='https://www.hemnet.se/maklare/fastighetsbyran-malmo-169/salda'
HEADERS={'User-Agent':'MalmoLiveDashboard/1.0 (public information; contact site owner for permission)'}

def fetch(url):
    r=requests.get(url,headers=HEADERS,timeout=25)
    r.raise_for_status()
    if 'text/html' not in r.headers.get('content-type','text/html'):
        raise ValueError('Unexpected content type')
    return BeautifulSoup(r.text,'html.parser')

def image_for(a,base):
    for img in a.select('img'):
        val=img.get('data-src') or img.get('src') or img.get('data-original')
        if not val:continue
        if val.startswith('//'):val='https:'+val
        val=urljoin(base,val)
        if urlparse(val).scheme=='https':return val
    return ''

def normalize(t):return ' '.join(t.split())

def get_fb(soup):
    out=[];seen=set()
    for a in soup.select('a[href]'):
        href=urljoin(FB,a.get('href',''))
        if not href.startswith('https://www.fastighetsbyran.com/') or 'objekt' not in href.lower():continue
        t=normalize(a.get_text(' ',strip=True))
        # Require a real property-style listing with room/area data.
        if not re.search(r'\b(?:rum|kvm)\b',t,re.I) or len(t)>500:continue
        address_match=re.search(r'(?:Se fler\s+)(.+?)(?=\s+(?:\d[\d\s]*\s*kr|\d+(?:[.,]\d+)?\s*rum|\d+(?:[.,]\d+)?\s*kvm))',t,re.I)
        if not address_match:continue
        address=address_match.group(1).strip()
        if not address or href in seen:continue
        seen.add(href)
        price=re.search(r'\d[\d\s]{3,}\s*kr',t)
        rooms=re.search(r'\d+(?:[.,]\d+)?\s*rum',t)
        area=re.search(r'\d+(?:[.,]\d+)?\s*kvm',t)
        out.append({'address':address,'area':' · '.join(x.group(0) for x in [rooms,area] if x),'price':price.group(0) if price else '', 'image':image_for(a,FB),'url':href,'status':'Budgivning pågår' if 'Budgivning pågår' in t else 'Till salu'})
    return out

def get_hemnet(soup):
    out=[];seen=set()
    for a in soup.select('a[href]'):
        href=urljoin(HN,a.get('href',''))
        if not href.startswith('https://www.hemnet.se/') or '/salda/' not in href:continue
        t=normalize(a.get_text(' ',strip=True))
        if 'Slutpris' not in t or len(t)>650:continue
        m=re.search(r'Såld\s+(\d{1,2}\s+[a-zåäö]+\.?\s+\d{4})\s+(.+?)\s+(\d+(?:[,.]\d+)?\s*m²)',t,re.I)
        if not m:continue
        address=m.group(2).strip()
        price=re.search(r'Slutpris\s+([\d\s\xa0]+\s*kr)',t,re.I)
        if href in seen:continue
        seen.add(href)
        out.append({'address':address,'area':m.group(3),'price':price.group(1).strip() if price else '', 'date':m.group(1),'image':image_for(a,HN),'url':href})
    return out

def read_json(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def main():
    old=read_json(OUT,{'newListings':[],'soldListings':[],'bids':[]})
    state=read_json(STATE,{'known':[],'initialized':False})
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    result={**old,'updatedAt':now,'sources':{'listings':FB,'sold':HN},'sourceStatus':{}}
    successes=0
    try:
        listings=get_fb(fetch(FB))
        if not listings:raise ValueError('No valid listing cards parsed; source markup may have changed')
        successes+=1
        known=set(state.get('known',[]))
        is_first=not state.get('initialized',False)
        fresh=[p for p in listings if p['url'] not in known]
        # On first run do not falsely call all properties newly listed.
        result['newListings']=[] if is_first else fresh[:12]
        result['bids']=[{'address':p['address'],'status':'Budgivning pågår','url':p['url'],'image':p['image'],'price':p['price']} for p in listings if p['status']=='Budgivning pågår'][:12]
        result['sourceStatus']['listings']='ok'
        state={'known':list((known | {p['url'] for p in listings}))[-5000:],'initialized':True}
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception as exc:
        result['sourceStatus']['listings']='error: '+str(exc)[:180]
        print('Listings:',exc,file=sys.stderr)
    try:
        sold=get_hemnet(fetch(HN))
        if not sold:raise ValueError('No sold property cards parsed; source markup may have changed')
        successes+=1
        result['soldListings']=sold[:12]
        result['sourceStatus']['sold']='ok'
    except Exception as exc:
        result['sourceStatus']['sold']='error: '+str(exc)[:180]
        print('Sold:',exc,file=sys.stderr)
    # Never overwrite valid historical feed when both upstreams fail.
    if not successes:
        print('No successful sources: preserving previous feed',file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Collected:',len(result['newListings']),'new;',len(result['bids']),'bids;',len(result['soldListings']),'sold; source successes',successes)
    return 0
if __name__=='__main__':sys.exit(main())
