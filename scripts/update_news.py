# Briefing Diário feed updater v3
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

GOOGLE_NEWS = 'https://news.google.com/rss/search?'
FALLBACK_FEEDS = {
    'Mundo': ['https://feeds.bbci.co.uk/news/world/rss.xml'],
    'África': ['https://feeds.bbci.co.uk/news/world/africa/rss.xml']
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

def parse_entries(section, entries):
    result = []
    for item in entries[:15]:
        title = clean(item.get('title',''))
        desc = clean(item.get('summary','') or item.get('description',''))
        if not title:
            continue
        source = item.get('source', {})
        if isinstance(source, dict):
            source = source.get('title','')
        result.append({
            'section': section,
            'tags': make_tags(title + ' ' + desc),
            'title': title,
            'summary': desc[:500],
            'why': 'Notícia recente com potencial relevância para decisões, negócios ou contexto estratégico.',
            'impact': 'Avaliar efeitos em energia, economia, segurança, emprego, tecnologia ou investimento.',
            'source': clean(source) or 'Fonte internacional',
            'published': clean(item.get('published','')),
            'link': item.get('link','')
        })
    return result

def read_google(section, query):
    # Evita os parâmetros regionais que provocaram feeds vazios no GitHub Actions.
    params = urlencode({'q': query, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
    url = GOOGLE_NEWS + params
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; BriefingDiario/2.0)'})
    with urlopen(req, timeout=30) as response:
        raw = response.read()
    feed = feedparser.parse(raw)
    return parse_entries(section, feed.entries)

def read_fallback(section, url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; BriefingDiario/2.0)'})
    with urlopen(req, timeout=30) as response:
        raw = response.read()
    feed = feedparser.parse(raw)
    return parse_entries(section, feed.entries)

items=[]
seen=set()
errors=[]
for section, query in QUERIES.items():
    section_items=[]
    try:
        section_items = read_google(section, query)
    except Exception as error:
        errors.append(f'{section}/Google: {type(error).__name__}: {error}')
    if not section_items:
        for feed_url in FALLBACK_FEEDS.get(section, []):
            try:
                section_items = read_fallback(section, feed_url)
                if section_items:
                    break
            except Exception as error:
                errors.append(f'{section}/fallback: {type(error).__name__}: {error}')
    for item in section_items:
        key=norm(item['title'])
        if key and key not in seen:
            seen.add(key)
            items.append(item)

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