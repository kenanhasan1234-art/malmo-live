from bs4 import BeautifulSoup
from fetch import get_fb,get_hemnet
fb='''<a href="/sv/sverige/till-salu/skane-lan/malmo-kommun/objekt/?objektID=123"><img src="https://example.org/1.jpg">Budgivning pågår Se fler Dagvattengatan 8C Hyllie 1 445 000 kr1.5 rum35 kvm</a>'''
hn='''<a href="/salda/bostader/123"><img src="https://example.org/2.jpg">Såld 7 okt. 2026 Nikolaigatan 5 U3 Malmö, Malmö kommun 43,6 m²1,5 rum Slutpris 1 820 000 kr 41 743 kr/m²Fastighetsbyrån Malmö</a>'''
a=get_fb(BeautifulSoup(fb,'html.parser'));b=get_hemnet(BeautifulSoup(hn,'html.parser'))
assert len(a)==1 and a[0]['status']=='Budgivning pågår',a
assert len(b)==1 and b[0]['price'].strip()=='1 820 000 kr',b
print('OK: listing, bidding and sold parsing fixtures')
