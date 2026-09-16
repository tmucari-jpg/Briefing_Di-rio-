import html, json, re, unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import feedparser

WINDOW_HOURS = 7 * 24
MIN_ITEMS = 8

CATEGORIES = {
    'Concursos': ['concurso público', 'tender', 'procurement', 'licitação', 'concurso', 'bid'],
    'Investimentos': ['investimento', 'investment', 'investidor', 'investors', 'capital', 'project finance'],
    'Novos projectos': ['novo projeto', 'novo projecto', 'new project', 'projecto', 'project', 'development'],
    'Empregos estratégicos': ['emprego', 'jobs', 'hiring', 'recrutamento', 'vacancy', 'vacancies', 'career'],
    'Financiamento': ['financiamento', 'finance', 'funding', 'grant', 'subvenção', 'loan', 'crédito'],
    'Energia/LNG': ['energia', 'energy', 'LNG', 'gás', 'gas', 'oil', 'petróleo', 'renewable'],
    'Tecnologia': ['tecnologia', 'technology', 'AI', 'artificial intelligence', 'digital', 'data centre'],
    'Procurement': ['procurement', 'supplier', 'fornecedor', 'tender', 'bid', 'compras'],
    'Expansão de empresas': ['expansão', 'expansion', 'new plant', 'factory', 'branch', 'market entry', 'opens'],
    'Regulação & decretos': ['decreto', 'decree', 'regulamento', 'regulation', 'lei', 'law', 'gazette', 'boletim'],
}

QUERIES_PT = [
    '(Moçambique OR Maputo OR Matola) (concurso OR licitação OR procurement OR tender) when:7d',
    '(Moçambique OR Maputo) (investimento OR projecto OR projeto OR expansão OR fábrica OR indústria) when:7d',
    '(Moçambique OR Maputo) (financiamento OR grant OR crédito OR fundo OR investimento) when:7d',
    '(Moçambique OR Cabo Delgado OR Nampula OR Tete) (energia OR LNG OR gás OR mineração) when:7d',
    '(Moçambique OR Maputo) (tecnologia OR inteligência artificial OR digital OR data center) when:7d',
    '(Moçambique OR Maputo) (emprego OR recrutamento OR vagas OR hiring) when:7d',
    '(Moçambique OR Maputo) (decreto OR regulamento OR lei OR regulação OR Boletim da República) when:7d',
    '(África OR Angola OR Tanzânia OR África do Sul) (investment OR project OR expansion OR procurement OR energy OR LNG) when:7d',
]

QUERIES_EN = [
    '(Mozambique OR Maputo) (tender OR procurement OR bid) when:7d',
    '(Mozambique OR Maputo) (investment OR project OR expansion OR factory OR industry) when:7d',
    '(Mozambique OR Maputo) (funding OR grant OR finance OR credit) when:7d',
    '(Mozambique OR Cabo Delgado OR Nampula OR Tete) (energy OR LNG OR gas OR mining) when:7d',
    '(Mozambique OR Maputo) (technology OR AI OR digital OR data centre) when:7d',
    '(Mozambique OR Maputo) (jobs OR hiring OR recruitment OR vacancies) when:7d',
    '(Mozambique OR Maputo) (decree OR regulation OR law OR gazette) when:7d',
    '(Africa OR Angola OR Tanzania OR South Africa) (investment OR project OR expansion OR procurement OR energy OR LNG) when:7d',
]

PT_SOURCES = [
    ('RTP Últimas', 'https://www.rtp.pt/noticias/rss'),
    ('RTP Mundo', 'https://www.rtp.pt/noticias/rss/mundo'),
    ('DW Português', 'https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html'),
    ('Club of Mozambique', 'https://clubofmozambique.com/feed/'),
]
EN_SOURCES = [
    ('BBC World', 'https://feeds.bbci.co.uk/news/world/rss.xml'),
    ('BBC Africa', 'https://feeds.bbci.co.uk/news/world/africa/rss.xml'),
    ('DW English', 'https://rss.dw.com/rdf/rss-en-all'),
    ('Club of Mozambique', 'https://clubofmozambique.com/feed/'),
]


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', s.lower()).encode('ascii', 'ignore').decode())


def dt(item):
    for k in ('published_parsed', 'updated_parsed'):
        v = item.get(k)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for k in ('published', 'updated'):
        try:
            x = parsedate_to_datetime(item.get(k, ''))
            return x.astimezone(timezone.utc) if x.tzinfo else x.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def age_hours(d):
    return (datetime.now(timezone.utc) - d).total_seconds() / 3600 if d else 99999


def category(title, desc):
    t = (title + ' ' + desc).lower()
    # Specific categories first to avoid generic business terms swallowing them.
    order = ['Regulação & decretos', 'Concursos', 'Procurement', 'Energia/LNG', 'Empregos estratégicos', 'Financiamento', 'Tecnologia', 'Expansão de empresas', 'Novos projectos', 'Investimentos']
    for c in order:
        if any(k in t for k in CATEGORIES[c]):
            return c
    return None


def score(title, desc, source):
    t = (title + ' ' + desc).lower()
    s = 0
    if any(k in t for k in ['moçambique', 'mozambique', 'maputo', 'cabo delgado', 'nampula', 'tete']): s += 5
    if any(k in t for k in ['tender', 'procurement', 'concurso', 'licitação', 'funding', 'grant', 'investment', 'investimento']): s += 3
    if any(k in t for k in ['decreto', 'decree', 'regulamento', 'regulation', 'lei', 'law', 'gazette']): s += 4
    if any(k in t for k in ['lng', 'energia', 'energy', 'gás', 'gas', 'mineração', 'mining']): s += 3
    if source.lower() in ('club of mozambique', 'rtp últimas', 'rtp mundo', 'dw português', 'bbc africa'): s += 1
    return s


def make_item(sec, title, desc, source, published, link):
    c = category(title, desc)
    if not c:
        return None
    t = (title + ' ' + desc).lower()
    if c == 'Concursos' or c == 'Procurement':
        action = 'Verificar requisitos, prazo e documentação antes de preparar uma proposta.'
    elif c == 'Empregos estratégicos':
        action = 'Verificar entidade recrutadora, requisitos, localização e prazo de candidatura.'
    elif c == 'Regulação & decretos':
        action = 'Confirmar o texto oficial e avaliar se altera obrigações, licenças, custos ou processos da empresa.'
    elif c in ('Investimentos', 'Novos projectos', 'Expansão de empresas', 'Energia/LNG'):
        action = 'Mapear empresas envolvidas, fornecedores necessários e próximos marcos do projecto.'
    elif c == 'Financiamento':
        action = 'Confirmar elegibilidade, montante, prazo e documentos exigidos pela entidade financiadora.'
    elif c == 'Tecnologia':
        action = 'Avaliar aplicação prática, fornecedores, competências necessárias e impacto na produtividade.'
    else:
        action = 'Avaliar relevância comercial e próximos passos.'
    return {
        'section': sec,
        'category': c,
        'title': title,
        'summary': desc[:600],
        'why': 'Pode representar uma oportunidade concreta de negócio, candidatura, fornecimento, emprego ou adaptação regulatória.',
        'action': action,
        'source': source,
        'published': published.isoformat(),
        'age_hours': round(max(0, age_hours(published)), 1),
        'link': link,
        'score': score(title, desc, source),
    }


def parse_feed(url, source, hours, sec):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 BriefingDiario/15', 'Accept': 'application/rss+xml, application/xml, text/xml, */*'})
    with urlopen(req, timeout=30) as r:
        raw = r.read()
    f = feedparser.parse(raw)
    out = []
    for i in f.entries:
        title = clean(i.get('title'))
        desc = clean(i.get('summary') or i.get('description'))
        d = dt(i)
        if not title or not d or age_hours(d) < 0 or age_hours(d) > hours:
            continue
        x = make_item(sec, title, desc, source, d, i.get('link', ''))
        if x:
            out.append(x)
    return out


def google(q, pt=True):
    cfg = {'hl': 'pt-PT', 'gl': 'MZ', 'ceid': 'MZ:pt-PT'} if pt else {'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'}
    u = 'https://news.google.com/rss/search?' + urlencode({'q': q, 'hl': cfg['hl'], 'gl': cfg['gl'], 'ceid': cfg['ceid']})
    return parse_feed(u, 'Google News', WINDOW_HOURS, 'Moçambique')


def build(lang):
    pt = lang == 'pt'
    sources = PT_SOURCES if pt else EN_SOURCES
    queries = QUERIES_PT if pt else QUERIES_EN
    items, seen = [], set()
    for source, url in sources:
        try:
            for x in parse_feed(url, source, WINDOW_HOURS, 'Moçambique'):
                k = norm(x['title'])
                if k and k not in seen:
                    seen.add(k); items.append(x)
        except Exception as e:
            print('feed', source, type(e).__name__, str(e)[:160])
    for q in queries:
        try:
            for x in google(q, pt):
                k = norm(x['title'])
                if k and k not in seen:
                    seen.add(k); items.append(x)
        except Exception as e:
            print('google', type(e).__name__, str(e)[:160])
    items.sort(key=lambda x: (x['score'], -x['age_hours']), reverse=True)
    # Keep a compact, useful weekly radar with category diversity.
    selected = []
    used = set()
    for c in CATEGORIES:
        choices = [x for x in items if x['category'] == c]
        if choices:
            selected.append(max(choices, key=lambda x: (x['score'], -x['age_hours'])))
            used.add(norm(selected[-1]['title']))
    for x in items:
        if len(selected) >= 15: break
        if norm(x['title']) not in used:
            selected.append(x); used.add(norm(x['title']))
    selected = sorted(selected[:15], key=lambda x: x['published'], reverse=True)
    return {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'language': lang,
        'window_days': 7,
        'items': selected,
        'categories': list(CATEGORIES),
        'note': 'Radar editorial: confirmar sempre o documento, concurso, vaga ou oportunidade na fonte original antes de agir.',
        'generator': 'GitHub Actions · Radar de Oportunidades',
    }


Path('docs/opportunities-pt.json').write_text(json.dumps(build('pt'), ensure_ascii=False, indent=2), encoding='utf-8')
Path('docs/opportunities-en.json').write_text(json.dumps(build('en'), ensure_ascii=False, indent=2), encoding='utf-8')
print('Radar de oportunidades actualizado.')
