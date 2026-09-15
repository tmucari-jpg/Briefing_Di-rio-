# Briefing Diário — atualização editorial das notícias
import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import feedparser

PRIMARY_HOURS = 24
FALLBACK_HOURS = 72
TARGET = {'Mundo': 4, 'África': 3, 'Moçambique': 3}

LANGS = {
    'pt': {'hl': 'pt-PT', 'gl': 'MZ', 'ceid': 'MZ:pt-PT', 'file': 'docs/news-pt.json'},
    'en': {'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en', 'file': 'docs/news-en.json'},
}

# Fontes diretas primeiro. RTP foi removida porque o endpoint anterior devolvia HTTPError.
RSS = {
    'pt': {
        'Mundo': [('BBC', 'https://feeds.bbci.co.uk/portuguese/international/rss.xml')],
        'África': [('BBC', 'https://feeds.bbci.co.uk/portuguese/topics/africa/rss.xml')],
        'Moçambique': [('O País', 'https://opais.co.mz/feed/'), ('Club of Mozambique', 'https://clubofmozambique.com/feed/')],
    },
    'en': {
        'Mundo': [('BBC', 'https://feeds.bbci.co.uk/news/world/rss.xml')],
        'África': [('BBC', 'https://feeds.bbci.co.uk/news/world/africa/rss.xml')],
        'Moçambique': [('Club of Mozambique', 'https://clubofmozambique.com/feed/')],
    },
}

THEMES = ['energy','energia','lng','gas','oil','petróleo','petroleo','econom','economy','economia','investment','investimento','business','negócios','trade','tariff','market','markets','artificial intelligence','inteligência artificial','inteligencia artificial','technology','tecnologia',' ai ','security','segurança','conflict','conflito','war','guerra','military','sanction','sanções','shipping','strait','infrastructure','infraestrutura','jobs','emprego','mining','mineração','climate','drought','flood','water','água','interest rate','inflation']
GLOBAL_ACTORS = ['china','united states','u.s.','usa','europe','european union','eu ','russia','ukraine','middle east','israel','iran','saudi','yemen','india','japan','south korea','uk','britain','nato','opec','world bank','imf','un','g7','g20']
AFRICA_ACTORS = ['africa','african','mozambique','moçambique','south africa','angola','tanzania','malawi','zambia','zimbabwe','kenya','nigeria','ghana','ethiopia','drc','congo','rwanda','uganda','somalia','sudan','egypt','algeria','morocco','senegal','namibia','botswana','djibouti','madagascar']
MOZ_ACTORS = ['mozambique','moçambique','maputo','cabo delgado','pemba','niassa','nampula','beira','nacala','tete','inhambane','gaza','manica','zambezia','rovuma','corredor de maputo','corredor de nacala']
BAD = ['emmy','celebrity','celebridades','futebol','football','sport','sports','cinema','filme','movie','novela','música','music','horóscopo','horoscope','receita','recipe','crime passional','estupro','rape','assalto','acidente doméstico','moda','fashion','reality show','influencer','casamento','namoro','irmãs','irmãos','documentário','documentary','entretenimento','entertainment']


def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()


def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', s.lower()).encode('ascii','ignore').decode())


def published_dt(item):
    for key in ('published_parsed','updated_parsed'):
        v = item.get(key)
        if v:
            try: return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception: pass
    for key in ('published','updated'):
        v = item.get(key,'')
        if v:
            try:
                dt = parsedate_to_datetime(v)
                return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception: pass
    return None


def age_hours(dt):
    return (datetime.now(timezone.utc)-dt).total_seconds()/3600 if dt else 9999


def is_fresh(item, hours):
    dt = published_dt(item)
    return dt is not None and age_hours(dt) <= hours


def tags(text):
    t=text.lower(); out=[]
    if any(x in t for x in ['energy','energia','lng','gas','oil','petróleo','petroleo']): out.append('Energia')
    if any(x in t for x in ['artificial intelligence','inteligência artificial','inteligencia artificial','technology','tecnologia',' ai ']): out.append('IA')
    if any(x in t for x in ['econom','investment','investimento','business','negócios','trade','market']): out.append('Economia')
    if any(x in t for x in ['security','segurança','conflict','conflito','war','guerra','military','sanction']): out.append('Segurança')
    return out or ['Economia']


def relevant(section,title,desc):
    t=f'{title} {desc}'.lower()
    if not any(x in t for x in THEMES): return False
    if any(x in t for x in BAD): return False
    if section=='Mundo': return any(x in t for x in GLOBAL_ACTORS) or any(x in t for x in ['oil','lng','gas','energy','artificial intelligence','ai ','war','guerra','sanction','tariff','interest rate','inflation'])
    if section=='África': return any(x in t for x in AFRICA_ACTORS)
    return any(x in t for x in MOZ_ACTORS)


def why_impact(section,text,lang):
    t=text.lower()
    if any(x in t for x in ['lng','gas','oil','energy','energia']):
        return (('É relevante porque pode mexer com preços, investimento e segurança energética.','Para Moçambique, importa pela exposição ao gás, energia, logística e receitas de exportação.') if lang=='pt' else ('It matters because it can affect prices, investment and energy security.','For Mozambique, it matters because of exposure to gas, energy, logistics and export revenues.'))
    if any(x in t for x in ['artificial intelligence','inteligência artificial','technology','tecnologia',' ai ']):
        return (('Pode acelerar ou travar investimento, regulação e adoção tecnológica.','Para Moçambique, interessa por produtividade, emprego digital, serviços públicos e novas oportunidades de negócio.') if lang=='pt' else ('It can accelerate or slow investment, regulation and technology adoption.','For Mozambique, it matters for productivity, digital jobs, public services and new business opportunities.'))
    if any(x in t for x in ['war','guerra','conflict','conflito','security','segurança','military','sanction']):
        return (('Pode alterar riscos geopolíticos, rotas comerciais, energia e custos de financiamento.','Moçambique pode sentir efeitos através de importações, energia, comércio regional e investimento.') if lang=='pt' else ('It can change geopolitical risks, trade routes, energy and financing costs.','Mozambique may feel effects through imports, energy, regional trade and investment.'))
    if section=='Moçambique':
        return (('É uma evolução diretamente ligada ao ambiente económico, social ou institucional do país.','Pode afetar investimento, emprego, fornecedores locais, custos ou previsibilidade para empresas e famílias.') if lang=='pt' else ('It is directly linked to Mozambique’s economic, social or institutional environment.','It may affect investment, jobs, local suppliers, costs or predictability for businesses and households.'))
    return (('Ajuda a acompanhar uma mudança relevante na economia e na geopolítica.','O impacto potencial para Moçambique deve ser acompanhado através de comércio, energia, investimento e condições financeiras.') if lang=='pt' else ('It helps track a relevant change in the economy and geopolitics.','Potential effects on Mozambique should be monitored through trade, energy, investment and financial conditions.'))


def parse_feed(url,section,lang,source,hours):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; BriefingDiario/7.0)'})
    with urlopen(req,timeout=25) as r: parsed=feedparser.parse(r.read())
    out=[]
    for item in parsed.entries:
        title=clean(item.get('title','')); desc=clean(item.get('summary','') or item.get('description','')); dt=published_dt(item)
        if not title or dt is None or age_hours(dt)>hours or not relevant(section,title,desc): continue
        text=title+' '+desc; why,impact=why_impact(section,text,lang)
        out.append({'section':section,'tags':tags(text),'title':title,'summary':desc[:700],'why':why,'impact':impact,'source':source,'published':dt.isoformat(),'age_hours':round(age_hours(dt),1),'within_24h':age_hours(dt)<=PRIMARY_HOURS,'link':item.get('link','')})
    return out


def google(section,query,lang,hours):
    cfg=LANGS[lang]
    q=query if hours<=24 else query.replace(' when:1d','')
    url='https://news.google.com/rss/search?'+urlencode({'q':q,'hl':cfg['hl'],'gl':cfg['gl'],'ceid':cfg['ceid']})
    return parse_feed(url,section,lang,'Google News',hours)


def add_unique(dst,new_items,seen,limit=50):
    for x in sorted(new_items,key=lambda z:z.get('published',''),reverse=True):
        k=norm(x['title'])
        if k and k not in seen:
            seen.add(k); dst.append(x)
            if len(dst)>=limit: break


def build(lang):
    by={s:[] for s in TARGET}; errors=[]
    for section in TARGET:
        seen=set()
        for source,url in RSS.get(lang,{}).get(section,[]):
            try: add_unique(by[section],parse_feed(url,section,lang,source,PRIMARY_HOURS),seen,20)
            except Exception as e: errors.append(f'{section}/{source}: {type(e).__name__}')
        queries={'Mundo':'oil LNG energy geopolitics AI trade sanctions markets when:1d','África':'Africa energy investment infrastructure security technology economy when:1d','Moçambique':'Mozambique Moçambique LNG energy investment projects jobs economy security when:1d'}
        try: add_unique(by[section],google(section,queries[section],lang,PRIMARY_HOURS),seen,20)
        except Exception as e: errors.append(f'{section}/Google: {type(e).__name__}')

    # Só usa 48–72h para preencher lacunas; as notícias das últimas 24h continuam prioritárias.
    if sum(len(v) for v in by.values())<10:
        for section in TARGET:
            for source,url in RSS.get(lang,{}).get(section,[]):
                try: add_unique(by[section],parse_feed(url,section,lang,source,FALLBACK_HOURS),seen,30)
                except Exception: pass
            try: add_unique(by[section],google(section,queries[section],lang,FALLBACK_HOURS),seen,30)
            except Exception: pass

    selected=[]
    for section,n in TARGET.items(): selected.extend(sorted(by[section],key=lambda x:(not x['within_24h'], -x['age_hours']))[:n])
    if len(selected)<10:
        pool=[x for s in TARGET for x in sorted(by[s],key=lambda z:(not z['within_24h'], -z['age_hours'])) if x not in selected]
        selected.extend(pool[:10-len(selected)])
    if len(selected)<10: raise SystemExit(f'Atualização {lang} insuficiente: {len(selected)} notícias. ' + ' | '.join(errors))
    selected=sorted(selected[:10],key=lambda x:(not x['within_24h'],x.get('published','')),reverse=False)
    selected=sorted(selected,key=lambda x:x.get('published',''),reverse=True)
    now=datetime.now(timezone.utc).isoformat(); pt=lang=='pt'
    payload={'updated_at':now,'language':lang,'window_hours':PRIMARY_HOURS,'fallback_hours':FALLBACK_HOURS,'items':selected,'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança','Tecnologia e IA'] if pt else ['Energy and LNG','Economy and investment','Geopolitics and security','Technology and AI'],'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'] if pt else ['Geopolitical shocks','Economic volatility','Unverified information risk'],'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento'] if pt else ['Energy and suppliers','Technology and AI','Jobs, business and investment'],'generator':'GitHub Actions · Briefing Diário','section_counts':{s:sum(1 for x in selected if x['section']==s) for s in TARGET}}
    Path(LANGS[lang]['file']).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); return payload

pt=build('pt'); en=build('en'); Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8')
print(f"PT: {len(pt['items'])} notícias; secções {pt['section_counts']}")
print(f"EN: {len(en['items'])} notícias; secções {en['section_counts']}")
print(f"UTC: {pt['updated_at']}")
