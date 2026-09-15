# Briefing Diário feed updater
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import feedparser

SECTIONS = {
    'Mundo': 'world geopolitics economy energy oil LNG artificial intelligence technology security when:1d',
    'África': 'Africa economy energy LNG investment infrastructure security jobs when:1d',
    'Moçambique': 'Mozambique Moçambique LNG energy economy projects jobs investment security when:1d',
}

LANGS = {
    'pt': {
        'hl': 'pt-PT', 'gl': 'MZ', 'ceid': 'MZ:pt-PT',
        'file': 'docs/news-pt.json',
        'source': 'Fonte internacional',
        'why': 'Ajuda a acompanhar decisões, riscos e oportunidades com possível impacto em Moçambique.',
        'impact': 'Avaliar efeitos em energia, economia, segurança, emprego, tecnologia e investimento.',
    },
    'en': {
        'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en',
        'file': 'docs/news-en.json',
        'source': 'International source',
        'why': 'Helps track decisions, risks and opportunities that may affect Mozambique.',
        'impact': 'Assess effects on energy, economy, security, jobs, technology and investment.',
    },
}

# Direct RSS sources are used as a fallback/supplement so one failing provider
# cannot stop the daily update.
RSS = {
    'pt': {
        'Mundo': [
            'https://feeds.bbci.co.uk/portuguese/international/rss.xml',
        ],
        'África': [
            'https://feeds.bbci.co.uk/portuguese/topics/africa/rss.xml',
        ],
    },
    'en': {
        'Mundo': [
            'https://feeds.bbci.co.uk/news/world/rss.xml',
        ],
        'África': [
            'https://feeds.bbci.co.uk/news/world/africa/rss.xml',
        ],
    },
}


def clean(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()


def norm(text):
    text = unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text)


def make_tags(text):
    text = text.lower()
    groups = {
        'Energia': ['energy', 'energia', 'lng', 'gas', 'oil', 'petróleo', 'petroleo'],
        'IA': ['artificial intelligence', 'inteligência artificial', 'inteligencia artificial', 'technology', 'tecnologia', 'ai '],
        'Economia': ['economy', 'economia', 'investment', 'investimento', 'business', 'negócios', 'negocios'],
        'Segurança': ['security', 'segurança', 'seguranca', 'conflict', 'guerra', 'military'],
    }
    return [tag for tag, words in groups.items() if any(word in text for word in words)] or ['Economia']


def parse_entries(section, entries, lang):
    cfg = LANGS[lang]
    result = []
    for item in entries:
        title = clean(item.get('title', ''))
        if not title:
            continue
        desc = clean(item.get('summary', '') or item.get('description', ''))
        source = item.get('source', '')
        if isinstance(source, dict):
            source = source.get('title', '')
        published = clean(item.get('published', '') or item.get('updated', ''))
        link = item.get('link', '')
        result.append({
            'section': section,
            'tags': make_tags(title + ' ' + desc),
            'title': title,
            'summary': desc[:600],
            'why': cfg['why'],
            'impact': cfg['impact'],
            'source': clean(source) or cfg['source'],
            'published': published,
            'link': link,
        })
    return result


def read_feed(url, section, lang):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; BriefingDiario/3.0)'})
    with urlopen(req, timeout=25) as response:
        raw = response.read()
    parsed = feedparser.parse(raw)
    if getattr(parsed, 'bozo', False) and not parsed.entries:
        raise RuntimeError('RSS inválido ou vazio')
    return parse_entries(section, parsed.entries, lang)


def google(section, query, lang):
    cfg = LANGS[lang]
    url = 'https://news.google.com/rss/search?' + urlencode({
        'q': query,
        'hl': cfg['hl'],
        'gl': cfg['gl'],
        'ceid': cfg['ceid'],
    })
    return read_feed(url, section, lang)


def add_unique(items, seen, new_items, limit=30):
    for item in new_items:
        key = norm(item['title'])
        if key and key not in seen:
            seen.add(key)
            items.append(item)
            if len(items) >= limit:
                break


def build_language(lang):
    items = []
    seen = set()
    errors = []

    for section, query in SECTIONS.items():
        section_items = []

        # Google News is the primary source because it gives broad coverage
        # and lets us request the selected language and recent results.
        try:
            section_items = google(section, query, lang)
        except Exception as exc:
            errors.append(f'{section}/Google: {type(exc).__name__}: {exc}')

        # Supplement, rather than merely replace, Google results with direct RSS.
        for url in RSS.get(lang, {}).get(section, []):
            if len(section_items) >= 10:
                break
            try:
                add_unique(section_items, set(norm(x['title']) for x in section_items), read_feed(url, section, lang), limit=15)
            except Exception as exc:
                errors.append(f'{section}/RSS: {type(exc).__name__}: {exc}')

        # If Google returned fewer than 10, try a second broader Google query.
        if len(section_items) < 10:
            try:
                broad = f'{section} latest news when:2d'
                add_unique(section_items, set(norm(x['title']) for x in section_items), google(section, broad, lang), limit=15)
            except Exception as exc:
                errors.append(f'{section}/Google-broad: {type(exc).__name__}: {exc}')

        add_unique(items, seen, section_items, limit=30)

    # A valid daily feed must contain enough stories for the app to show its
    # intended 10-story edition. Fail loudly only if the whole update is empty.
    if len(items) < 10:
        details = ' | '.join(errors[-8:])
        raise SystemExit(f'Actualização {lang} insuficiente: apenas {len(items)} notícias. {details}')

    now = datetime.now(timezone.utc).isoformat()
    if lang == 'pt':
        watch = ['Energia e LNG', 'Economia e investimento', 'Geopolítica e segurança']
        risks = ['Choques geopolíticos', 'Volatilidade económica', 'Risco de informação não verificada']
        opportunities = ['Energia e fornecedores', 'Tecnologia e IA', 'Emprego, negócios e investimento']
    else:
        watch = ['Energy and LNG', 'Economy and investment', 'Geopolitics and security']
        risks = ['Geopolitical shocks', 'Economic volatility', 'Unverified information risk']
        opportunities = ['Energy and suppliers', 'Technology and AI', 'Jobs, business and investment']

    payload = {
        'updated_at': now,
        'language': lang,
        'items': items,
        'watch': watch,
        'risks': risks,
        'opportunities': opportunities,
        'generator': 'GitHub Actions · Briefing Diário',
    }
    Path(LANGS[lang]['file']).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return payload


pt_payload = build_language('pt')
en_payload = build_language('en')

# Keep news.json as a compatibility feed. The app uses the language-specific
# files, while older links/caches can still receive the Portuguese edition.
Path('docs/news.json').write_text(
    json.dumps(pt_payload, ensure_ascii=False, indent=2),
    encoding='utf-8',
)

print(f"Actualizado pt: {len(pt_payload['items'])} notícias")
print(f"Actualizado en: {len(en_payload['items'])} notícias")
print(f"Timestamp UTC: {pt_payload['updated_at']}")
