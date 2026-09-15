import json, re, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

TARGET={'Mundo':4,'África':2,'Moçambique':2}
MIN_NEWS=8
SOURCE_SCORE={'RTP Notícias':5,'RTP':5,'DW Português':5,'BBC World':5,'BBC Africa':5,'Club of Mozambique':4,'Google News':2}
BAD_WORDS=('futebol','football','cinema','filme','música','music','novela','horóscopo','horoscope','moda','fashion','entretenimento','entertainment')

def norm(s):
    s=unicodedata.normalize('NFKD',s.lower()).encode('ascii','ignore').decode()
    s=re.sub(r'[^a-z0-9 ]','',s)
    return re.sub(r'\s+',' ',s).strip()

def source_score(s):
    for k,v in SOURCE_SCORE.items():
        if k.lower() in s.lower(): return v
    return 2

def recency_score(x):
    h=max(0,float(x.get('age_hours',999)))
    return max(0,24-h)/24*5 if h<=24 else max(0,72-h)/48*1.5

def relevance_score(x):
    text=(x.get('title','')+' '+x.get('summary','')).lower(); score=0
    for w in ('lng','gás','gas','energy','energia','oil','econom','investment','investimento','business','trade','technology','tecnologia','artificial intelligence','security','segurança','war','guerra','diplomacy','diplomacia','infrastructure','infraestrutura','jobs','employment','emprego','mining','mineração'): 
        if w in text: score+=1
    if x.get('section')=='Moçambique' and any(w in text for w in ('moçambique','mozambique','maputo','cabo delgado','pemba')): score+=3
    elif x.get('section')=='África' and any(w in text for w in ('africa','afric','angola','tanzania','tanzânia','south africa','áfrica do sul')): score+=2
    return min(score,8)

def valid(x):
    title=x.get('title','').strip(); summary=x.get('summary','').strip(); link=x.get('link','').strip(); source=x.get('source','').strip()
    if len(title)<25 or len(title)>220 or len(summary)<40 or not link or not source: return False
    if any(w in (title+' '+summary).lower() for w in BAD_WORDS): return False
    try:
        d=datetime.fromisoformat(x['published'].replace('Z','+00:00'))
        if d>datetime.now(timezone.utc): return False
    except: return False
    return bool(x.get('why')) and bool(x.get('impact'))

def dedupe(items):
    out=[]
    for x in sorted(items,key=lambda z:z.get('published',''),reverse=True):
        a=norm(x.get('title',''))
        if not a: continue
        if any(a==norm(y.get('title','')) or SequenceMatcher(None,a,norm(y.get('title',''))).ratio()>=0.86 for y in out): continue
        out.append(x)
    return out

def curate(d):
    items=dedupe([x for x in d.get('items',[]) if valid(x)])
    for x in items:
        x['editorial_score']=round(source_score(x.get('source',''))+recency_score(x)+relevance_score(x),2)
        x['source_tier']='A' if source_score(x.get('source',''))>=5 else ('B' if source_score(x.get('source',''))>=4 else 'C')
    items.sort(key=lambda x:x['editorial_score'],reverse=True)
    counts={s:0 for s in TARGET}; selected=[]
    for s,n in TARGET.items():
        choices=[x for x in items if x['section']==s]; selected.extend(choices[:n]); counts[s]=min(len(choices),n)
    if any(counts[s]<n for s,n in TARGET.items()): raise SystemExit(f'Qualidade editorial rejeitada: secções insuficientes {counts}.')
    chosen_ids={id(x) for x in selected}; rest=[x for x in items if id(x) not in chosen_ids]
    selected.extend(rest[:max(0,10-len(selected))]); selected=sorted(selected[:10],key=lambda x:x['editorial_score'],reverse=True)
    if len(selected)<MIN_NEWS: raise SystemExit(f'Qualidade editorial rejeitada: apenas {len(selected)} notícias válidas.')
    d['items']=selected; d['section_counts']={s:sum(x['section']==s for x in selected) for s in TARGET}
    d['editorial']='Curadoria automática: relevância + actualidade + qualidade da fonte + deduplicação + validação.'
    d['briefing_intro']={'pt':'Bom dia. Este é o Briefing Diário. Hoje, vale a pena acompanhar primeiro os temas com maior impacto potencial em geopolítica, economia, energia, tecnologia e Moçambique.','en':'Good morning. This is the Daily Briefing. Today, focus first on the stories with the strongest potential relevance to geopolitics, the economy, energy, technology and Mozambique.'}
    return d

for name in ('news-pt.json','news-en.json'):
    p=Path('docs')/name; d=json.loads(p.read_text(encoding='utf-8')); curate(d); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
pt=json.loads(Path('docs/news-pt.json').read_text(encoding='utf-8')); Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8'); print('Editorial OK:',pt['section_counts'],len(pt['items']))