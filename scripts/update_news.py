import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
import xml.etree.ElementTree as ET

QUERIES = {
    'Mundo': 'global geopolitics economy energy oil LNG artificial intelligence technology security when:1d',
    'África': 'Africa economy energy LNG investment infrastructure security jobs when:1d',
    'Moçambique': 'Mozambique LNG energy economy projects jobs investment security when:1d'
}

def clean(text):
    return re.sub(r'\\s+', ' ', re.sub(r'<[^>]+>', '', text or '')).strip()

def make_tags(text):
    text = text.lower()
    result = []
    groups = {
        'Energia': ['energy', 'energia', 'lng', 'gas', 'oil', 'petróleo'],
        'IA': ['artificial intelligence', 'inteligência artificial', 'technology', 'tecnologia'],
        'Economia': ['economy', 'economia', 'investment', 'investimento', 'business', 'negócios'],
        'Segurança': ['security', 'segurança', 'conflict', 'guerra', 'military']
    }
    for tag, words in groups.items():
        if any(word in text for word in words):
            result.append(tag)
    return result or ['Economia']

def read_feed(section, query):
    url = 'https://news.google.com/rss/search?q=' + quote(query) + '&hl=pt-PT&gl=MZ&ceid=MZ:pt-419'
    root = ET.fromstring(urlopen(url, timeout=20).read())
    result = []
    for item in root.findall('./channel/item')[:15]:
        title = clean(item.findtext('title'))
        desc = clean(item.findtext('description'))
        result.append({
            'section': section,
            'tags': make_tags(title + ' ' + desc),
            'title': title,
            'summary': desc[:500],
            'why': 'Contextualizar o impacto da notícia e a relevância para Moçambique.',
            'impact': 'Avaliar efeitos em energia, economia, segurança, emprego ou investimento.',
            'source': clean(item.findtext('source')) or 'Google News',
            'link': item.findtext('link') or ''
        })
    return result

items = []
seen = set()
for section, query in QUERIES.items():
    try:
        for item in read_feed(section, query):
            key = re.sub(r'[^a-z0-9]', '', item['title'].lower())
            if key and key not in seen:
                seen.add(key)
                items.append(item)
    except Exception as error:
        print(section, error)

payload = {
    'updated_at': datetime.now(timezone.utc).isoformat(),
    'items': items,
    'watch': ['Energia e LNG', 'Economia e investimento', 'Geopolítica e segurança'],
    'risks': ['Choques geopolíticos', 'Volatilidade económica', 'Risco de informação não verificada'],
    'opportunities': ['Energia e fornecedores', 'Tecnologia e IA', 'Emprego, negócios e investimento']
}
Path('docs/news.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print('Actualizadas', len(items), 'notícias')
