import html, json, re, shutil, subprocess, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

import feedparser

PRIMARY_HOURS = 24
FALLBACK_HOURS = 96
MIN_TARGET = {'Moçambique': 4, 'África': 3, 'Mundo': 3}
DESIRED_TARGET = {'Moçambique': 6, 'África': 6, 'Mundo': 6}
MAX_PER_SOURCE = 3
FEED_CACHE = {}

RSS_PT = {
    'Moçambique': [('Diário Económico','https://www.diarioeconomico.co.mz/feed/'),('O País','https://opais.co.mz/feed/'),('AIM News','https://aimnews.org/feed/'),('Jornal Notícias','https://jornalnoticias.co.mz/feed/'),('Checka','https://checka.co.mz/feed/'),('Club of Mozambique','https://clubofmozambique.com/feed/')],
    'África': [('ONU News','https://news.un.org/feed/subscribe/pt/news/all/rss.xml'),('Euronews Português','https://pt.euronews.com/rss?level=theme&name=news'),('O País','https://opais.co.mz/feed/'),('RTP Notícias','https://www.rtp.pt/noticias/rss/mundo'),('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html')],
    'Mundo': [('ONU News','https://news.un.org/feed/subscribe/pt/news/all/rss.xml'),('Euronews Português','https://pt.euronews.com/rss?level=theme&name=news'),('RTP Notícias','https://www.rtp.pt/noticias/rss/mundo'),('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html')],
}
RSS_EN = {
    'Moçambique': [('Club of Mozambique','https://clubofmozambique.com/feed/'),('AIM News','https://aimnews.org/feed/'),('Le Monde Mozambique','https://www.lemonde.fr/en/mozambique/rss_full.xml')],
    'África': [('BBC Africa','https://feeds.bbci.co.uk/news/world/africa/rss.xml'),('Al Jazeera English','https://www.aljazeera.com/xml/rss/all.xml'),('DW English','https://rss.dw.com/rdf/rss-en-all')],
    'Mundo': [('BBC World','https://feeds.bbci.co.uk/news/world/rss.xml'),('DW English','https://rss.dw.com/rdf/rss-en-all'),('Al Jazeera English','https://www.aljazeera.com/xml/rss/all.xml')],
}

THEMES = ['energy','energia','lng','gás','gas','oil','petróleo','petroleo','fuel','combustível','combustivel','econom','investment','investimento','business','negócios','trade','comércio','market','mercado','artificial intelligence','inteligência artificial','technology','tecnologia','security','segurança','conflito','conflict','war','guerra','military','militar','sanction','sanções','infrastructure','infraestrutura','jobs','emprego','employment','mining','mineração','climate','drought','flood','water','água','interest rate','inflation','inflação','tariff','tarifas','election','eleição','eleições','governo','government','diplomacia','diplomacy','refugiados','refugees']
AFRICA = ['africa','áfrica','african','south africa','áfrica do sul','angola','tanzania','tanzânia','malawi','zambia','zâmbia','zimbabwe','zimbabué','kenya','quénia','nigeria','nigéria','ghana','ethiopia','etiópia','congo','rwanda','ruanda','uganda','somalia','somália','sudan','sudão','egypt','egipto','morocco','marrocos','senegal','namibia','namíbia','botswana','eswatini','lesotho','cabo verde']
MOZ = ['moçambique','mozambique','maputo','chapo','cabo delgado','pemba','niassa','nampula','nacala','tete','beira','inhambane','gaza','manica','zambézia','zambezia','rovuma','quelimane','matola']
BAD = ['futebol','football','sport','sports','uefa','fifa','cinema','filme','movie','novela','música','music','horóscopo','horoscope','receita','recipe','moda','fashion','entretenimento','entertainment','concurso público','solicitação de propostas','manifestação de interesse','consulta pública','tender','procurement']
EN_WORDS = [' the ',' and ',' of ',' to ',' for ',' with ',' says ',' from ',' are ',' is ',' has ',' have ',' will ',' after ',' over ',' into ',' africa\'s ']
PT_WORDS = [' de ',' da ',' do ',' das ',' dos ',' para ',' com ',' que ',' uma ',' um ',' foi ',' será ',' estão ',' sobre ',' após ',' entre ',' país ',' governo ']
STOPWORDS = set('a o as os de da do das dos e em no na nos nas por para com sem sobre entre que uma um uns umas ao aos à às se é foi são será após mais menos como seu sua seus suas the and of to for with from are is has have will after over into says new'.split())
PLACE_MARKERS=('mocambique','maputo','cabo delgado','tigray','etiopia','marrocos','angola','tanzania','malawi','zambia','zimbabwe','quenia','nigeria','ghana','congo','ruanda','uganda','somalia','sudao','egipto','namibia','botswana','arabia saudita','medio oriente','estados unidos','eua','portugal','franca','paris')
EVENT_GROUPS={
 'eleições':('eleicao','eleicoes','eleitoral','eleitorais','parlamento','partido'),
 'conflito':('guerra','conflito','rebeldes','forcas','armados','terrorismo','ataque'),
 'energia':('energia','energetico','combustivel','petroleo','gas','lng','electricidade','electrificacao'),
 'economia':('economia','investimento','inflacao','mercado','comercio','financiamento'),
 'tecnologia':('tecnologia','digital','inteligencia artificial','ia','telecomunicacoes'),
}

def clean(value): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value or ''))).strip()
def norm(value):
    value=unicodedata.normalize('NFKD',value.lower()).encode('ascii','ignore').decode()
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]',' ',value)).strip()
def published_at(item):
    for key in ('published_parsed','updated_parsed'):
        value=item.get(key)
        if value:
            try: return datetime(*value[:6],tzinfo=timezone.utc)
            except Exception: pass
    for key in ('published','updated'):
        try:
            value=parsedate_to_datetime(item.get(key,''))
            return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        except Exception: pass
    return None
def age_hours(value): return (datetime.now(timezone.utc)-value).total_seconds()/3600 if value else 99999
def language_ok(title,summary,pt):
    text=f' {title} {summary} '.lower()
    en_score=sum(marker in text for marker in EN_WORDS)
    pt_score=sum(marker in text for marker in PT_WORDS)
    return pt_score>=2 and pt_score>=en_score if pt else en_score>=2 and en_score>=pt_score
def relevant(section,title,summary):
    text=f'{title} {summary}'.lower()
    if any(term in text for term in BAD) or not any(term in text for term in THEMES): return False
    if section=='Moçambique': return any(term in text for term in MOZ)
    if section=='África': return not any(term in text for term in MOZ) and any(term in text for term in AFRICA)
    return not any(term in text for term in MOZ) and not any(term in text for term in AFRICA)
def tags(text):
    text=text.lower(); result=[]
    if any(x in text for x in ['energy','energia','lng','gás','gas','oil','petróleo','fuel','combustível']): result.append('Energia')
    if any(x in text for x in ['artificial intelligence','inteligência artificial','technology','tecnologia']): result.append('IA')
    if any(x in text for x in ['econom','investment','investimento','business','negócios','trade','comércio','market','inflation','emprego']): result.append('Economia')
    if any(x in text for x in ['security','segurança','conflict','conflito','war','guerra','sanction','sanções','diplomacia']): result.append('Segurança')
    return result or ['Economia']
def short_title(value,limit=105):
    value=clean(value).strip(' .')
    return value if len(value)<=limit else value[:limit].rsplit(' ',1)[0]+'…'
def context(section,title,text,pt):
    text=text.lower()
    subject=f'«{short_title(title)}»'
    if not pt:
        if any(x in text for x in ['lng','gas','oil','energy','fuel']): return f'{subject} matters because it may change energy and investment decisions affecting {section}.',f'For {subject}, the effects may reach prices, projects, suppliers and supply chains connected to {section}.'
        if any(x in text for x in ['artificial intelligence','technology']): return f'{subject} points to a concrete change in the adoption, regulation or use of technology.',f'For {subject}, the effects may include changes in skills demand, productivity, costs and digital opportunities in {section}.'
        if any(x in text for x in ['war','conflict','security','sanction','diplomacy']): return f'{subject} deserves attention because it may change political, diplomatic or security risks.',f'For {subject}, the effects may reach trade, movement, investment and supply chains connected to {section}.'
        if any(x in text for x in ['econom','investment','business','trade','market','inflation','employment']): return f'{subject} helps explain a concrete economic or business change relevant to {section}.',f'For {subject}, the effects may reach prices, demand, finance, hiring or supplier opportunities.'
        return f'{subject} is worth following because of its possible economic, institutional or regional effects.',f'For {subject}, the impact will depend on what happens next, but it may affect decisions, costs or opportunities in {section}.'
    if any(x in text for x in ['lng','gás','gas','oil','energy','energia','fuel','combustível']):
        return f'{subject} merece atenção porque pode alterar decisões de energia e investimento em {section}.',f'No caso de {subject}, os efeitos podem chegar aos preços, projectos, fornecedores e cadeias de abastecimento ligados a {section}.'
    if any(x in text for x in ['artificial intelligence','inteligência artificial','technology','tecnologia']): return f'{subject} é relevante por mostrar uma mudança concreta na adopção, regulação ou uso da tecnologia.',f'No caso de {subject}, os efeitos podem incluir mudanças nas competências procuradas, produtividade, custos e oportunidades digitais em {section}.'
    if any(x in text for x in ['war','guerra','conflict','conflito','security','segurança','sanction','sanções','diplomacia']): return f'{subject} merece acompanhamento porque pode mudar o nível de risco político, diplomático ou de segurança.',f'No caso de {subject}, os efeitos podem chegar ao comércio, circulação, investimento e cadeias de abastecimento com ligação a {section}.'
    if any(x in text for x in ['econom','investment','investimento','business','trade','comércio','market','inflation','emprego']): return f'{subject} ajuda a perceber uma mudança económica ou empresarial concreta com relevância para {section}.',f'No caso de {subject}, os efeitos podem chegar aos preços, procura, financiamento, contratação ou oportunidades para fornecedores.'
    return f'{subject} merece acompanhamento pelo possível efeito económico, institucional ou regional.',f'No caso de {subject}, o impacto dependerá dos próximos desenvolvimentos, mas poderá afectar decisões, custos ou oportunidades em {section}.'
def event_tokens(value):
    return {word for word in norm(value).split() if len(word)>=4 and word not in STOPWORDS}
def event_profile(item):
    text=norm(item['title']+' '+item['summary'])
    places={place for place in PLACE_MARKERS if place in text}
    groups={name for name,signals in EVENT_GROUPS.items() if any(signal in text for signal in signals)}
    return places,groups
def duplicate(candidate,seen):
    title=norm(candidate['title']); title_tokens=event_tokens(candidate['title']); body_tokens=event_tokens(candidate['title']+' '+candidate['summary'])
    candidate_places,candidate_groups=event_profile(candidate)
    for other in seen:
        other_title=norm(other['title']); other_title_tokens=event_tokens(other['title']); other_body_tokens=event_tokens(other['title']+' '+other['summary'])
        other_places,other_groups=event_profile(other)
        title_overlap=len(title_tokens & other_title_tokens)/max(1,min(len(title_tokens),len(other_title_tokens)))
        body_overlap=len(body_tokens & other_body_tokens)/max(1,min(len(body_tokens),len(other_body_tokens)))
        same_event=bool(candidate_places & other_places) and bool(candidate_groups & other_groups)
        if title==other_title or SequenceMatcher(None,title,other_title).ratio()>=.70 or title_overlap>=.60 or body_overlap>=.68 or same_event:return True
    return False
def parse(url,section,source,hours,pt):
    if url in FEED_CACHE:
        raw=FEED_CACHE[url]
        if raw is None: return []
    else:
        request=Request(url,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/16','Accept':'application/rss+xml, application/xml, text/xml, */*'})
        if shutil.which('curl'):
            result=subprocess.run(
                ['curl','-fsSL','--max-time','12','-A','Mozilla/5.0 BriefingDiario/17',url],
                capture_output=True,check=False
            )
            raw=result.stdout if result.returncode == 0 else b''
        else:
            raw=b''
        if not raw:
            try:
                with urlopen(request,timeout=10) as response: raw=response.read()
            except Exception:
                FEED_CACHE[url]=None
                raise
        FEED_CACHE[url]=raw
    feed=feedparser.parse(raw); output=[]; now=datetime.now(timezone.utc)
    for entry in feed.entries:
        title=clean(entry.get('title')); summary=clean(entry.get('summary') or entry.get('description')); published=published_at(entry)
        if not title or len(summary)<40 or not published or published>now or age_hours(published)>hours: continue
        if not relevant(section,title,summary) or not language_ok(title,summary,pt): continue
        link=entry.get('link','').strip()
        if not link.startswith(('http://','https://')) or 'news.google.com' in link.lower(): continue
        why,impact=context(section,title,f'{title} {summary}',pt)
        output.append({'section':section,'tags':tags(f'{title} {summary}'),'title':title,'summary':summary[:700],'why':why,'impact':impact,'source':source,'published':published.isoformat(),'age_hours':round(max(0,age_hours(published)),1),'within_24h':age_hours(published)<=24,'link':link,'original_source':True})
    return output
def add(destination,seen,items):
    for item in sorted(items,key=lambda value:value['published'],reverse=True):
        if item['title'] and not duplicate(item,seen): seen.append(item); destination.append(item)
def build(language):
    pt=language=='pt'; feeds=RSS_PT if pt else RSS_EN; grouped={section:[] for section in MIN_TARGET}; seen=[]
    for section in MIN_TARGET:
        for source,url in feeds[section]:
            try: add(grouped[section],seen,parse(url,section,source,PRIMARY_HOURS,pt))
            except Exception as error: print('feed',source,section,type(error).__name__,str(error)[:160])
    if any(len(grouped[section])<DESIRED_TARGET[section] for section in MIN_TARGET):
        for section in MIN_TARGET:
            for source,url in feeds[section]:
                try: add(grouped[section],seen,parse(url,section,source,FALLBACK_HOURS,pt))
                except Exception as error: print('fallback',source,section,type(error).__name__,str(error)[:160])
    missing={section:MIN_TARGET[section]-len(grouped[section]) for section in MIN_TARGET if len(grouped[section])<MIN_TARGET[section]}
    if missing: raise SystemExit(f'Actualização {language} rejeitada: secções insuficientes {missing}.')
    selected=[]
    for section,amount in DESIRED_TARGET.items():
        chosen=[]; counts={}
        for item in sorted(grouped[section],key=lambda value:value['published'],reverse=True):
            if counts.get(item['source'],0)>=MAX_PER_SOURCE: continue
            chosen.append(item); counts[item['source']]=counts.get(item['source'],0)+1
            if len(chosen)==amount: break
        for item in grouped[section]:
            if len(chosen)==amount: break
            if item not in chosen: chosen.append(item)
        distinct_sources={item['source'] for item in chosen}
        if len(distinct_sources)<2:
            raise SystemExit(f'Actualização {language} rejeitada: {section} tem apenas {len(distinct_sources)} fonte distinta.')
        selected.extend(chosen)
    selected=sorted(selected,key=lambda value:value['published'],reverse=True)
    payload={'updated_at':datetime.now(timezone.utc).isoformat(),'language':language,'window_hours':24,'fallback_hours':FALLBACK_HOURS,'items':selected,'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança','Tecnologia e IA'],'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'],'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento'],'generator':'GitHub Actions · Briefing Diário','section_counts':{section:sum(item['section']==section for item in selected) for section in MIN_TARGET}}
    return payload

if __name__ == '__main__':
    try:
        pt=build('pt'); en=build('en')
    except SystemExit as error:
        print(f'AVISO: {error} Mantida a última edição válida.')
        raise SystemExit(0)
    Path('docs/news-pt.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('docs/news-en.json').write_text(json.dumps(en,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PT',pt['section_counts'],len(pt['items']),'EN',en['section_counts'],len(en['items']))
