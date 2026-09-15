# Briefing Diário feed updater
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import feedparser

QUERIES = {
    'Mundo': 'world geopolitics economy energy oil LNG artificial intelligence technology security when:1d',
    'África': 'Africa economy energy LNG investment infrastructure security jobs when:1d',
    'Moçambique': 'Mozambique Moçambique LNG energy economy projects jobs investment security when:1d'
}

LANGS = {
    'pt': {'hl':'pt-PT','gl':'MZ','ceid':'MZ:pt-PT','file':'docs/news-pt.json'},
    'en': {'hl':'en-US','gl':'US','ceid':'US:en','file':'docs/news-en.json'}
}

FALLBACK_FEEDS = {
    'en': {'Mundo':'https://feeds.bbci.co.uk/news/world/rss.xml','África':'https://feeds.bbci.co.uk/news/world/africa/rss.xml'},
    'pt': {'Mundo':'https://feeds.bbci.co.uk/portuguese/international/rss.xml','África':'https://feeds.bbci.co.uk/portuguese/topics/africa/rss.xml'}
}

def clean(text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text or '')).strip()

def norm(text):
    text = unicodedata.normalize('NFKD', text.lower()).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text)

def make_tags(text):
    text = text.lower()
    groups = {
        'Energia': ['energy','energia','lng','gas','oil','petróleo','petroleo'],
        'IA': ['artificial intelligence','inteligência artificial','inteligencia artificial','technology','tecnologia','ai '],
        'Economia': ['economy','economia','investment','investimento','business','negócios','negocios'],
        'Segurança': ['security','segurança','seguranca','conflict','guerra','military']
    }
    return [tag for tag, words in groups.items() if any(word in text for word in words)] or ['Economia']

def parse_entries(section, entries, lang):
    result=[]
    for item in entries[:15]:
        title=clean(item.get('title',''))
        desc=clean(item.get('summary','') or item.get('description',''))
        if not title: continue
        source=item.get('source',{})
        if isinstance(source,dict): source=source.get('title','')
        result.append({'section':section,'tags':make_tags(title+' '+desc),'title':title,'summary':desc[:500],
            'why':'Notícia recente com potencial relevância para decisões, negócios ou contexto estratégico.' if lang=='pt' else 'Recent news with potential relevance for decisions, business or strategic context.',
            'impact':'Avaliar efeitos em energia, economia, segurança, emprego, tecnologia ou investimento.' if lang=='pt' else 'Assess effects on energy, economy, security, jobs, technology or investment.',
            'source':clean(source) or 'Fonte internacional','published':clean(item.get('published','')),'link':item.get('link','')})
    return result

def read_feed(url, section, lang):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; BriefingDiario/2.0)'})
    with urlopen(req,timeout=30) as response: raw=response.read()
    return parse_entries(section,feedparser.parse(raw).entries,lang)

def google(section, query, lang):
    cfg=LANGS[lang]
    url='https://news.google.com/rss/search?'+urlencode({'q':query,'hl':cfg['hl'],'gl':cfg['gl'],'ceid':cfg['ceid']})
    return read_feed(url,section,lang)

for lang,cfg in LANGS.items():
    items=[]; seen=set(); errors=[]
    for section,query in QUERIES.items():
        got=[]
        try: got=google(section,query,lang)
        except Exception as e: errors.append(f'{section}/Google: {type(e).__name__}: {e}')
        if not got and section in FALLBACK_FEEDS.get(lang,{}):
            try: got=read_feed(FALLBACK_FEEDS[lang][section],section,lang)
            except Exception as e: errors.append(f'{section}/fallback: {type(e).__name__}: {e}')
        for item in got:
            key=norm(item['title'])
            if key and key not in seen: seen.add(key); items.append(item)
    if not items:
        raise SystemExit(f'Nenhuma notícia foi obtida para {lang}. '+' | '.join(errors))
    payload={'updated_at':datetime.now(timezone.utc).isoformat(),'language':lang,'items':items,
      'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança'] if lang=='pt' else ['Energy and LNG','Economy and investment','Geopolitics and security'],
      'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'] if lang=='pt' else ['Geopolitical shocks','Economic volatility','Unverified information risk'],
      'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento'] if lang=='pt' else ['Energy and suppliers','Technology and AI','Jobs, business and investment']}
    Path(cfg['file']).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Actualizado',lang,len(items),'notícias')