# Briefing Diário feed updater
import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import feedparser

SECTIONS = {
    'Mundo': 'world geopolitics economy energy oil LNG artificial intelligence technology security climate trade markets when:1d',
    'África': 'Africa economy energy LNG investment infrastructure security technology jobs when:1d',
    'Moçambique': 'Mozambique Moçambique LNG energy economy projects jobs investment security technology when:1d',
}

LANGS = {
    'pt': {'hl': 'pt-PT', 'gl': 'MZ', 'ceid': 'MZ:pt-PT', 'file': 'docs/news-pt.json', 'source': 'Fonte internacional'},
    'en': {'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en', 'file': 'docs/news-en.json', 'source': 'International source'},
}

RSS = {
    'pt': {
        'Mundo': [('BBC', 'https://feeds.bbci.co.uk/portuguese/international/rss.xml')],
        'África': [('BBC', 'https://feeds.bbci.co.uk/portuguese/topics/africa/rss.xml')],
    },
    'en': {
        'Mundo': [('BBC', 'https://feeds.bbci.co.uk/news/world/rss.xml')],
        'África': [('BBC', 'https://feeds.bbci.co.uk/news/world/africa/rss.xml')],
    },
}

RELEVANCE = {
    'Mundo': ['geopolit', 'econom', 'market', 'trade', 'tariff', 'oil', 'gas', 'lng', 'energy', 'ai', 'artificial intelligence', 'technology', 'semiconductor', 'cyber', 'security', 'military', 'war', 'conflict', 'climate', 'sanction', 'interest rate', 'inflation', 'investment', 'supply', 'shipping', 'strait', 'china', 'united states', 'europe', 'middle east', 'ukraine', 'russia'],
    'África': ['africa', 'african', 'econom', 'market', 'investment', 'energy', 'lng', 'gas', 'oil', 'infrastructure', 'technology', 'ai', 'security', 'military', 'conflict', 'jobs', 'trade', 'mining', 'cobalt', 'copper', 'uranium', 'gold', 'climate', 'drought', 'flood', 'china', 'eu', 'world bank', 'imf'],
    'Moçambique': ['mozambique', 'moçambique', 'maputo', 'cabo delgado', 'niassa', 'pemba', 'beira', 'nacala', 'lng', 'gas', 'energy', 'energia', 'econom', 'investment', 'investimento', 'project', 'projeto', 'infrastructure', 'infraestrutura', 'jobs', 'emprego', 'business', 'negócios', 'technology', 'ai', 'security', 'segurança', 'terror', 'mining', 'mineração', 'coal', 'carvão', 'port', 'porto', 'logistics', 'agriculture', 'water', 'água', 'korea', 'china', 'world bank', 'imf'],
}

BAD = ['emmy', 'celebrity', 'celebridades', 'futebol', 'football', 'sport', 'sports', 'cinema', 'filme', 'movie', 'novela', 'música', 'music', 'horóscopo', 'horoscope', 'receita', 'recipe', 'crime passional', 'estupro', 'rape', 'assalto', 'acidente doméstico', 'vacina', 'vaccine', 'saúde', 'health', 'moda', 'fashion', 'reality show', 'influencer']


def clean(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()


def norm(text):
    text = unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text)


def make_tags(text):
    t = text.lower()
    groups = {
        'Energia': ['energy', 'energia', 'lng', 'gas', 'oil', 'petróleo', 'petroleo'],
        'IA': ['artificial intelligence', 'inteligência artificial', 'inteligencia artificial', 'technology', 'tecnologia', 'ai '],
        'Economia': ['economy', 'economia', 'investment', 'investimento', 'business', 'negócios', 'negocios', 'market', 'trade'],
        'Segurança': ['security', 'segurança', 'seguranca', 'conflict', 'guerra', 'war', 'military', 'terror'],
    }
    return [tag for tag, words in groups.items() if any(word in t for word in words)] or ['Economia']


def relevant(section, title, desc):
    t = f'{title} {desc}'.lower()
    if any(b in t for b in BAD) and not any(k in t for k in RELEVANCE[section]):
        return False
    return any(k in t for k in RELEVANCE[section])


def parse_entries(section, entries, lang, source_name=''):
    cfg = LANGS[lang]
    result = []
    for item in entries:
        title = clean(item.get('title', ''))
        desc = clean(item.get('summary', '') or item.get('description', ''))
        if not title or not relevant(section, title, desc):
            continue
        published = clean(item.get('published', '') or item.get('updated', ''))
        link = item.get('link', '')
        result.append({
            'section': section,
            'tags': make_tags(title + ' ' + desc),
            'title': title,
            'summary': desc[:600],
            'why': 'Ajuda a acompanhar decisões, riscos e oportunidades que podem afetar Moçambique.' if lang == 'pt' else 'Helps track decisions, risks and opportunities that may affect Mozambique.',
            'impact': 'Avaliar efeitos potenciais em energia, economia, segurança, emprego, tecnologia e investimento.' if lang == 'pt' else 'Assess potential effects on energy, economy, security, jobs, technology and investment.',
            'source': clean(source_name) or cfg['source'],
            'published': published,
            'link': link,
        })
    return result


def read_feed(url, section, lang, source_name=''):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; BriefingDiario/4.0)'})
    with urlopen(req, timeout=25) as response:
        raw = response.read()
    parsed = feedparser.parse(raw)
    if not parsed.entries:
        raise RuntimeError('RSS vazio')
    return parse_entries(section, parsed.entries, lang, source_name)


def google(section, query, lang):
    cfg = LANGS[lang]
    url = 'https://news.google.com/rss/search?' + urlencode({'q': query, 'hl': cfg['hl'], 'gl': cfg['gl'], 'ceid': cfg['ceid']})
    return read_feed(url, section, lang, 'Google News')


def add_unique(items, seen, new_items, limit=30):
    for item in new_items:
        key = norm(item['title'])
        if key and key not in seen:
            seen.add(key)
            items.append(item)
            if len(items) >= limit:
                break


def recent_only(items, hours=30):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for x in items:
        p = x.get('published', '')
        try:
            dt = datetime.strptime(p, '%a, %d %b %Y %H:%M:%S %Z').replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                out.append(x)
        except Exception:
            # Keep entries whose feed timestamp cannot be parsed; the source has already supplied recency.
            out.append(x)
    return out


def build_language(lang):
    items, seen, errors = [], set(), []
    for section, query in SECTIONS.items():
        section_items = []
        try:
            section_items = google(section, query, lang)
        except Exception as exc:
            errors.append(f'{section}/Google: {type(exc).__name__}: {exc}')
        for source_name, url in RSS.get(lang, {}).get(section, []):
            if len(section_items) >= 10:
                break
            try:
                add_unique(section_items, {norm(x['title']) for x in section_items}, read_feed(url, section, lang, source_name), limit=15)
            except Exception as exc:
                errors.append(f'{section}/RSS: {type(exc).__name__}: {exc}')
        section_items = recent_only(section_items)
        if len(section_items) < 10:
            try:
                broad = f'{section} energy economy investment technology security latest when:1d'
                add_unique(section_items, {norm(x['title']) for x in section_items}, google(section, broad, lang), limit=15)
            except Exception as exc:
                errors.append(f'{section}/Google2: {type(exc).__name__}: {exc}')
        add_unique(items, seen, section_items, limit=30)

    if len(items) < 10:
        details = ' | '.join(errors[-8:])
        raise SystemExit(f'Atualização {lang} insuficiente: apenas {len(items)} notícias. {details}')

    now = datetime.now(timezone.utc).isoformat()
    if lang == 'pt':
        watch = ['Energia e LNG', 'Economia e investimento', 'Geopolítica e segurança', 'Tecnologia e IA']
        risks = ['Choques geopolíticos', 'Volatilidade económica', 'Risco de informação não verificada']
        opportunities = ['Energia e fornecedores', 'Tecnologia e IA', 'Emprego, negócios e investimento']
    else:
        watch = ['Energy and LNG', 'Economy and investment', 'Geopolitics and security', 'Technology and AI']
        risks = ['Geopolitical shocks', 'Economic volatility', 'Unverified information risk']
        opportunities = ['Energy and suppliers', 'Technology and AI', 'Jobs, business and investment']

    payload = {'updated_at': now, 'language': lang, 'items': items[:10], 'watch': watch, 'risks': risks, 'opportunities': opportunities, 'generator': 'GitHub Actions · Briefing Diário'}
    Path(LANGS[lang]['file']).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


pt_payload = build_language('pt')
en_payload = build_language('en')
Path('docs/news.json').write_text(json.dumps(pt_payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Actualizado pt: {len(pt_payload['items'])} notícias")
print(f"Actualizado en: {len(en_payload['items'])} notícias")
print(f"Timestamp UTC: {pt_payload['updated_at']}")
