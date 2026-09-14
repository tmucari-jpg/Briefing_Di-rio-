# Briefing Diário feed updater v2
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

def clean(text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text or '')).strip()

def norm(text):
    text = unicodedata.normalize('NFKD', text.lower()).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text)

def make_tags(text):
    text = text.lower()
    groups = {
        'Energia': ['energy','energia','lng','gas','oil','petróleo','petroleo'],
        'IA': ['artificial intelligence','inteligência artificial','inteligencia artificial','technology','tecnologia'],
        'Economia': ['economy','economia','investment','investimento','business','negócios','negocios'],
        'Segurança': ['security','segurança','seguranca','conflict','guerra','military']
    }
    return [tag for tag, words in groups.items() if any(word in text for word in words)] or ['Economia']

def read_feed(section, query):
    params = urlencode({'q': query, 'hl': 'pt-PT', 'gl': 'MZ', 'ceid': 'MZ:pt-419'})
    url = 'https://news.google.com/rss/search?' + params
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; BriefingDiario/1.0)'})
    feed = feedparser.parse(urlopen(req, timeout=30).read())
    result = []
    for item in feed.entries[:15]:
        title = clean(item.get('title',''))
        desc = clean(item.get('summary',''))
        if not title:
            continue
        result.append({
            'section': section,
            'tags': make_tags(title + ' ' + desc),
            'title': title,
            'summary': desc[:500],
            'why': 'Notícia recente com potencial relevância para decisões, negócios ou contexto estratégico.',
            'impact': 'Avaliar efeitos em energia, economia, segurança, emprego, tecnologia ou investimento.',
            'source': clean(item.get('source',{}).get('title','')) or 'Google News',
            'published': clean(item.get('published','')),
            'link': item.get('link','')
        })
    return result

items=[];seen=set();errors=[]
for section, query in QUERIES.items():
    try:
        for item in read_feed(section, query):
            key=norm(item['title'])
            if key and key not in seen:
                seen.add(key)
                items.append(item)
    except Exception as error:
        errors.append(f'{section}: {error}')

if not items:
    raise SystemExit('Nenhuma notícia foi obtida. ' + ' | '.join(errors))

payload={
 'updated_at':datetime.now(timezone.utc).isoformat(),
 'items':items,
 'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança'],
 'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'],
 'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento']
}
Path('docs/news.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('Actualizadas',len(items),'notícias')