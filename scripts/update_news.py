import html, json, re, shutil, subprocess, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

import feedparser

PRIMARY_HOURS = 24
FALLBACK_HOURS = 48
CARRY_FORWARD_HOURS = 0
MIN_TARGET = {'Moçambique': 0, 'África': 0, 'Mundo': 0}
DESIRED_TARGET = {'Moçambique': 5, 'África': 5, 'Mundo': 5}
MAX_PER_SOURCE = 2
MAX_EVENT_AGE_HOURS = 48
FEED_CACHE = {}
ARTICLE_CACHE = {}

RSS_PT = {
    'Moçambique': [('Diário Económico','https://www.diarioeconomico.co.mz/feed/'),('O País','https://opais.co.mz/feed/'),('AIM Notícias','https://aimnews.org/feed/'),('Jornal Notícias','https://jornalnoticias.co.mz/feed/'),('Checka','https://checka.co.mz/feed/'),('Club of Mozambique','https://clubofmozambique.com/feed/')],
    'África': [('Notícias ONU','https://news.un.org/feed/subscribe/pt/news/all/rss.xml'),('Euronews Português','https://pt.euronews.com/rss?level=theme&name=news'),('O País','https://opais.co.mz/feed/'),('RTP Notícias','https://www.rtp.pt/noticias/rss/mundo'),('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html')],
    'Mundo': [('Notícias ONU','https://news.un.org/feed/subscribe/pt/news/all/rss.xml'),('Euronews Português','https://pt.euronews.com/rss?level=theme&name=news'),('RTP Notícias','https://www.rtp.pt/noticias/rss/mundo'),('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html')],
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
PLACE_MARKERS=('mocambique','maputo','cabo delgado','pemba','beira','manganhe','tigray','etiopia','marrocos','angola','tanzania','malawi','zambia','zimbabwe','quenia','kenya','nigeria','ghana','congo','ruanda','uganda','somalia','sudao','egipto','namibia','botswana','africa do sul','south africa','arabia saudita','ira','iran','israel','ucrania','ukraine','russia','russia','franca','france','portugal','espanha','spain','reino unido','united kingdom','paris','bissau','guine bissau','senegal','argelia','argelia','tunisia','libia','egipto','ethiopia','sudan','saudi arabia','qatar','coreia do sul','south korea','estados unidos','eua','united states','china','india','japao','japan','europa','europe')
EVENT_GROUPS={
 'eleições':('eleicao','eleicoes','eleitoral','eleitorais','parlamento','partido'),
 'conflito':('guerra','conflito','rebeldes','forcas','armados','terrorismo','ataque'),
 'energia':('energia','energetico','combustivel','petroleo','gas','lng','electricidade','electrificacao'),
 'economia':('economia','investimento','inflacao','mercado','comercio','financiamento'),
 'tecnologia':('tecnologia','digital','inteligencia artificial','ia','telecomunicacoes'),
}

def clean(value):
    value=html.unescape(re.sub(r'<[^>]+>',' ',value or ''))
    value=re.sub(r'\bThe post\b.*$','',value,flags=re.I)
    value=re.sub(r'\bappeared first on\b.*$','',value,flags=re.I)
    value=re.sub(r'\bfirst appeared on\b.*$','',value,flags=re.I)
    value=re.sub(r'\b(?:read|ler) more\b.*$','',value,flags=re.I)
    return re.sub(r'\s+',' ',value).strip(' .[…')
def compact_summary(value,limit=1100):
    value=clean(value)
    if not value:return ''
    sentences=re.split(r'(?<=[.!?])\s+',value)
    selected=[]; size=0
    for sentence in sentences:
        sentence=sentence.strip()
        if not sentence:continue
        if selected and (size+len(sentence)+1>limit or len(selected)>=6):break
        selected.append(sentence); size+=len(sentence)+1
    result=' '.join(selected) or value
    if len(result)>limit:result=result[:limit].rsplit(' ',1)[0].rstrip(' ,;:')+'…'
    return result
def informative_summary(entry,limit=1100):
    candidates=[clean(entry.get('summary')),clean(entry.get('description'))]
    for content in entry.get('content',[]) or []:
        if isinstance(content,dict):candidates.append(clean(content.get('value')))
    candidates=[value for value in candidates if value]
    if not candidates:return ''
    return compact_summary(max(candidates,key=len),limit)
def json_article_bodies(value):
    output=[]
    def visit(node):
        if isinstance(node,dict):
            body=node.get('articleBody')
            if isinstance(body,str):output.append(body)
            for child in node.values():visit(child)
        elif isinstance(node,list):
            for child in node:visit(child)
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',value,flags=re.I|re.S):
        try:visit(json.loads(html.unescape(block.strip())))
        except Exception:pass
    return output
def article_summary(link,current,pt):
    if len(current)>=500:return current
    if link in ARTICLE_CACHE:return ARTICLE_CACHE[link] or current
    raw=b''
    if shutil.which('curl'):
        result=subprocess.run(['curl','-fsSL','--max-time','10','--max-filesize','2500000','-A','Mozilla/5.0 BriefingDiario/18',link],capture_output=True,check=False)
        raw=result.stdout if result.returncode==0 else b''
    if not raw:
        try:
            request=Request(link,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/18'})
            with urlopen(request,timeout=8) as response:raw=response.read(2500000)
        except Exception:pass
    if not raw:ARTICLE_CACHE[link]=''; return current
    page=raw.decode('utf-8','ignore'); candidates=[]
    for tag in re.findall(r'<meta\b[^>]*>',page,flags=re.I):
        if re.search(r'(?:name|property)=["\'](?:description|og:description|twitter:description)["\']',tag,flags=re.I):
            match=re.search(r'content=["\'](.*?)["\']',tag,flags=re.I|re.S)
            if match:candidates.append(match.group(1))
    candidates.extend(json_article_bodies(page))
    article_match=re.search(r'<article\b[^>]*>(.*?)</article>',page,flags=re.I|re.S)
    if article_match:
        paragraphs=[clean(value) for value in re.findall(r'<p\b[^>]*>(.*?)</p>',article_match.group(1),flags=re.I|re.S)]
        candidates.append(' '.join(value for value in paragraphs if len(value)>=35))
    candidates=[compact_summary(value) for value in candidates]
    candidates=[value for value in candidates if len(value)>len(current)+80 and language_ok('',value,pt)]
    enriched=max(candidates,key=len) if candidates else current
    ARTICLE_CACHE[link]=enriched
    return enriched
def localize_pt(value):
    replacements=((r'\bfake news\b','notícias falsas'),(r'\bchartered financial analyst\b','analista financeiro certificado'),(r'\bcfa charter award ceremony\b','cerimónia de atribuição da certificação CFA'),(r'\bprocurement\b','aquisições'),(r'\bbusiness\b','negócios'),(r'\bmarket\b','mercado'),(r'\binvestment\b','investimento'),(r'\bproject\b','projecto'),(r'\bservices\b','serviços'),(r'\bsupply\b','fornecimento'),(r'\bmanagement\b','gestão'),(r'\bsupport\b','apoio'),(r'\bdeadline\b','prazo'),(r'\bnew\b','novo'),(r'\band\b','e'))
    for pattern,replacement in replacements:value=re.sub(pattern,replacement,value,flags=re.I)
    return value
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
TOPIC_RULES={
    'Energia': ('energy','energia','lng','gás','gas','oil','petróleo','petroleo','fuel','combustível','combustivel','electricidade','electrificacao','refinery','refinaria'),
    'IA': ('artificial intelligence','inteligência artificial','machine learning','aprendizagem automática','technology','tecnologia','digital','telecom'),
    'Economia': ('econom','investment','investimento','business','negócios','trade','comércio','market','mercado','inflation','inflação','currency','divisas','financing','financiamento','employment','emprego','mining','mineração'),
    'Segurança': ('security','segurança','conflict','conflito','war','guerra','military','militar','attack','ataque','sanction','sanções','terrorism','terrorismo','diplomacy','diplomacia','refugee','refugiado')
}
NOISE_RULES=('futebol','football','cinema','filme','movie','música','music','novela','horóscopo','horoscope','moda','fashion','entretenimento','entertainment','celebrity','celebridades')
CONTEXT_RULES=('background','context','analysis','explainer','explained','what you need to know','por dentro','análise','analise','contexto','explicador')

def classify_topic(title,summary):
    text=norm(f'{title} {summary}')
    def has_term(term):
        term=norm(term)
        if ' ' in term:
            return term in text
        return re.search(r'\\b'+re.escape(term)+r'\\b',text) is not None
    scores={topic:sum(1 for term in terms if has_term(term)) for topic,terms in TOPIC_RULES.items()}
    ordered=sorted(scores.items(),key=lambda pair:pair[1],reverse=True)
    primary=ordered[0][0] if ordered and ordered[0][1] else 'Geral'
    secondary=[topic for topic,score in ordered[1:] if score and score>=max(1,ordered[0][1]-1)]
    return primary,secondary,scores

def editorial_type(title,summary,published,within_24h):
    text=norm(f'{title} {summary}')
    if any(norm(term) in text for term in NOISE_RULES):
        return 'noise'
    if any(norm(term) in text for term in CONTEXT_RULES) and not within_24h:
        return 'context'
    return 'event' if within_24h else 'update'

def relevant(section,title,summary):
    text=f'{title} {summary}'.lower()
    if any(term in text for term in BAD): return False
    primary,secondary,scores=classify_topic(title,summary)
    if primary=='Geral' and not secondary: return False
    if section=='Moçambique': return any(term in text for term in MOZ)
    if section=='África': return not any(term in text for term in MOZ) and any(term in text for term in AFRICA)
    return not any(term in text for term in MOZ) and not any(term in text for term in AFRICA)
def tags(text):
    primary,secondary,_=classify_topic(text,'')
    result=[] if primary=='Geral' else [primary]
    result.extend(x for x in secondary if x not in result)
    return result or ['Geral']

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
def exact_duplicate(candidate,seen):
    title=norm(candidate['title'])
    link=norm(candidate.get('link',''))
    for other in seen:
        if title and title==norm(other.get('title','')): return True
        if link and link==norm(other.get('link','')): return True
        if SequenceMatcher(None,title,norm(other.get('title',''))).ratio()>=.86: return True
    return False

def event_profile(item):
    text=norm(item.get('title','')+' '+item.get('summary',''))
    places={place for place in PLACE_MARKERS if place in text}
    groups={name for name,signals in EVENT_GROUPS.items() if any(signal in text for signal in signals)}
    return places,groups

def event_similarity(a,b):
    at=event_tokens(a.get('title','')); bt=event_tokens(b.get('title',''))
    ab=event_tokens(a.get('title','')+' '+a.get('summary','')); bb=event_tokens(b.get('title','')+' '+b.get('summary',''))
    places_a,groups_a=event_profile(a); places_b,groups_b=event_profile(b)
    title_overlap=len(at & bt)/max(1,min(len(at),len(bt)))
    body_overlap=len(ab & bb)/max(1,min(len(ab),len(bb)))
    shared_groups=groups_a & groups_b
    shared_places=places_a & places_b
    try:
        ta=datetime.fromisoformat(a['published'].replace('Z','+00:00'))
        tb=datetime.fromisoformat(b['published'].replace('Z','+00:00'))
        close_in_time=abs((ta-tb).total_seconds())/3600 <= MAX_EVENT_AGE_HOURS
    except Exception:
        close_in_time=True
    if not close_in_time:
        return 0

    # Topic alone is never enough. "Energy", "security" or "elections"
    # can describe many unrelated events on the same day.
    if title_overlap>=.58:
        return .95
    if body_overlap>=.68 and shared_places:
        return .92
    if shared_places and shared_groups and title_overlap>=.22:
        return .88
    if shared_places and shared_groups and body_overlap>=.45:
        return .84
    return 0

def cluster_events(items):
    clusters=[]
    for item in sorted(items,key=lambda value:value.get('published',''),reverse=True):
        match=None; best=0
        for cluster in clusters:
            score=max(event_similarity(item,member) for member in cluster['members'])
            if score>best:
                best=score; match=cluster
        if match is not None and best>=.74:
            match['members'].append(item)
        else:
            clusters.append({'members':[item]})

    output=[]
    for index,cluster in enumerate(clusters,1):
        members=cluster['members']
        primary=members[0]
        sources=[]
        for member in members:
            source=member.get('source','')
            if source and source not in sources: sources.append(source)
        primary=dict(primary)
        primary['event_id']=f"evt-{primary.get('section','').lower().replace('ç','c')}-{index:03d}"
        primary['cluster_size']=len(members)
        primary['source_count']=len(sources)
        primary['sources']=sources
        primary['primary_source']=primary.get('source')
        primary['status']=primary.get('editorial_type','event'); primary['topic_primary']=primary.get('topic_primary') or classify_topic(primary.get('title',''),primary.get('summary',''))[0]
        if len(members)>1:
            confirmations=[]
            for member in members[1:3]:
                confirmations.append({
                    'source':member.get('source'),
                    'title':member.get('title'),
                    'link':member.get('link')
                })
            primary['confirmations']=confirmations
        output.append(primary)
    return output

def add(destination,seen,items):
    for item in sorted(items,key=lambda value:value['published'],reverse=True):
        if item['title'] and not exact_duplicate(item,seen):
            seen.append(item)
            destination.append(item)

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
        title=clean(entry.get('title')); summary=informative_summary(entry); published=published_at(entry)
        if pt:title=localize_pt(title); summary=localize_pt(summary)
        if not title or len(summary)<40 or not published or published>now or age_hours(published)>hours: continue
        if not relevant(section,title,summary) or not language_ok(title,summary,pt): continue
        link=entry.get('link','').strip()
        if not link.startswith(('http://','https://')) or 'news.google.com' in link.lower(): continue
        why,impact=context(section,title,f'{title} {summary}',pt)
        topic_primary,topic_secondary,topic_scores=classify_topic(title,summary); editorial_status=editorial_type(title,summary,published,age_hours(published)<=24); output.append({'section':section,'tags':tags(f'{title} {summary}'),'topic_primary':topic_primary,'topic_secondary':topic_secondary,'topic_scores':topic_scores,'editorial_type':editorial_status,'title':title,'summary':summary[:1100],'why':why,'impact':impact,'source':source,'published':published.isoformat(),'age_hours':round(max(0,age_hours(published)),1),'within_24h':age_hours(published)<=24,'link':link,'original_source':True})
    return output
import html, json, re, shutil, subprocess, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

import feedparser

PRIMARY_HOURS = 24
FALLBACK_HOURS = 48
CARRY_FORWARD_HOURS = 0
MIN_TARGET = {'Moçambique': 0, 'África': 0, 'Mundo': 0}
DESIRED_TARGET = {'Moçambique': 5, 'África': 5, 'Mundo': 5}
MAX_PER_SOURCE = 2
MAX_EVENT_AGE_HOURS = 48
FEED_CACHE = {}
ARTICLE_CACHE = {}

RSS_PT = {
    'Moçambique': [('Diário Económico','https://www.diarioeconomico.co.mz/feed/'),('O País','https://opais.co.mz/feed/'),('AIM Notícias','https://aimnews.org/feed/'),('Jornal Notícias','https://jornalnoticias.co.mz/feed/'),('Checka','https://checka.co.mz/feed/'),('Club of Mozambique','https://clubofmozambique.com/feed/')],
    'África': [('Notícias ONU','https://news.un.org/feed/subscribe/pt/news/all/rss.xml'),('Euronews Português','https://pt.euronews.com/rss?level=theme&name=news'),('O País','https://opais.co.mz/feed/'),('RTP Notícias','https://www.rtp.pt/noticias/rss/mundo'),('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html')],
    'Mundo': [('Notícias ONU','https://news.un.org/feed/subscribe/pt/news/all/rss.xml'),('Euronews Português','https://pt.euronews.com/rss?level=theme&name=news'),('RTP Notícias','https://www.rtp.pt/noticias/rss/mundo'),('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html')],
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
PLACE_MARKERS=('mocambique','maputo','cabo delgado','pemba','beira','manganhe','tigray','etiopia','marrocos','angola','tanzania','malawi','zambia','zimbabwe','quenia','kenya','nigeria','ghana','congo','ruanda','uganda','somalia','sudao','egipto','namibia','botswana','africa do sul','south africa','arabia saudita','ira','iran','israel','ucrania','ukraine','russia','russia','franca','france','portugal','espanha','spain','reino unido','united kingdom','paris','bissau','guine bissau','senegal','argelia','argelia','tunisia','libia','egipto','ethiopia','sudan','saudi arabia','qatar','coreia do sul','south korea','estados unidos','eua','united states','china','india','japao','japan','europa','europe')
EVENT_GROUPS={
 'eleições':('eleicao','eleicoes','eleitoral','eleitorais','parlamento','partido'),
 'conflito':('guerra','conflito','rebeldes','forcas','armados','terrorismo','ataque'),
 'energia':('energia','energetico','combustivel','petroleo','gas','lng','electricidade','electrificacao'),
 'economia':('economia','investimento','inflacao','mercado','comercio','financiamento'),
 'tecnologia':('tecnologia','digital','inteligencia artificial','ia','telecomunicacoes'),
}

def clean(value):
    value=html.unescape(re.sub(r'<[^>]+>',' ',value or ''))
    value=re.sub(r'\bThe post\b.*$','',value,flags=re.I)
    value=re.sub(r'\bappeared first on\b.*$','',value,flags=re.I)
    value=re.sub(r'\bfirst appeared on\b.*$','',value,flags=re.I)
    value=re.sub(r'\b(?:read|ler) more\b.*$','',value,flags=re.I)
    return re.sub(r'\s+',' ',value).strip(' .[…')
def compact_summary(value,limit=1100):
    value=clean(value)
    if not value:return ''
    sentences=re.split(r'(?<=[.!?])\s+',value)
    selected=[]; size=0
    for sentence in sentences:
        sentence=sentence.strip()
        if not sentence:continue
        if selected and (size+len(sentence)+1>limit or len(selected)>=6):break
        selected.append(sentence); size+=len(sentence)+1
    result=' '.join(selected) or value
    if len(result)>limit:result=result[:limit].rsplit(' ',1)[0].rstrip(' ,;:')+'…'
    return result
def informative_summary(entry,limit=1100):
    candidates=[clean(entry.get('summary')),clean(entry.get('description'))]
    for content in entry.get('content',[]) or []:
        if isinstance(content,dict):candidates.append(clean(content.get('value')))
    candidates=[value for value in candidates if value]
    if not candidates:return ''
    return compact_summary(max(candidates,key=len),limit)
def json_article_bodies(value):
    output=[]
    def visit(node):
        if isinstance(node,dict):
            body=node.get('articleBody')
            if isinstance(body,str):output.append(body)
            for child in node.values():visit(child)
        elif isinstance(node,list):
            for child in node:visit(child)
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',value,flags=re.I|re.S):
        try:visit(json.loads(html.unescape(block.strip())))
        except Exception:pass
    return output
def article_summary(link,current,pt):
    if len(current)>=500:return current
    if link in ARTICLE_CACHE:return ARTICLE_CACHE[link] or current
    raw=b''
    if shutil.which('curl'):
        result=subprocess.run(['curl','-fsSL','--max-time','10','--max-filesize','2500000','-A','Mozilla/5.0 BriefingDiario/18',link],capture_output=True,check=False)
        raw=result.stdout if result.returncode==0 else b''
    if not raw:
        try:
            request=Request(link,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/18'})
            with urlopen(request,timeout=8) as response:raw=response.read(2500000)
        except Exception:pass
    if not raw:ARTICLE_CACHE[link]=''; return current
    page=raw.decode('utf-8','ignore'); candidates=[]
    for tag in re.findall(r'<meta\b[^>]*>',page,flags=re.I):
        if re.search(r'(?:name|property)=["\'](?:description|og:description|twitter:description)["\']',tag,flags=re.I):
            match=re.search(r'content=["\'](.*?)["\']',tag,flags=re.I|re.S)
            if match:candidates.append(match.group(1))
    candidates.extend(json_article_bodies(page))
    article_match=re.search(r'<article\b[^>]*>(.*?)</article>',page,flags=re.I|re.S)
    if article_match:
        paragraphs=[clean(value) for value in re.findall(r'<p\b[^>]*>(.*?)</p>',article_match.group(1),flags=re.I|re.S)]
        candidates.append(' '.join(value for value in paragraphs if len(value)>=35))
    candidates=[compact_summary(value) for value in candidates]
    candidates=[value for value in candidates if len(value)>len(current)+80 and language_ok('',value,pt)]
    enriched=max(candidates,key=len) if candidates else current
    ARTICLE_CACHE[link]=enriched
    return enriched
def localize_pt(value):
    replacements=((r'\bfake news\b','notícias falsas'),(r'\bchartered financial analyst\b','analista financeiro certificado'),(r'\bcfa charter award ceremony\b','cerimónia de atribuição da certificação CFA'),(r'\bprocurement\b','aquisições'),(r'\bbusiness\b','negócios'),(r'\bmarket\b','mercado'),(r'\binvestment\b','investimento'),(r'\bproject\b','projecto'),(r'\bservices\b','serviços'),(r'\bsupply\b','fornecimento'),(r'\bmanagement\b','gestão'),(r'\bsupport\b','apoio'),(r'\bdeadline\b','prazo'),(r'\bnew\b','novo'),(r'\band\b','e'))
    for pattern,replacement in replacements:value=re.sub(pattern,replacement,value,flags=re.I)
    return value
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
def exact_duplicate(candidate,seen):
    title=norm(candidate['title'])
    link=norm(candidate.get('link',''))
    for other in seen:
        if title and title==norm(other.get('title','')): return True
        if link and link==norm(other.get('link','')): return True
        if SequenceMatcher(None,title,norm(other.get('title',''))).ratio()>=.86: return True
    return False

def event_profile(item):
    text=norm(item.get('title','')+' '+item.get('summary',''))
    places={place for place in PLACE_MARKERS if place in text}
    groups={name for name,signals in EVENT_GROUPS.items() if any(signal in text for signal in signals)}
    return places,groups

def event_similarity(a,b):
    at=event_tokens(a.get('title','')); bt=event_tokens(b.get('title',''))
    ab=event_tokens(a.get('title','')+' '+a.get('summary','')); bb=event_tokens(b.get('title','')+' '+b.get('summary',''))
    places_a,groups_a=event_profile(a); places_b,groups_b=event_profile(b)
    title_overlap=len(at & bt)/max(1,min(len(at),len(bt)))
    body_overlap=len(ab & bb)/max(1,min(len(ab),len(bb)))
    shared_groups=groups_a & groups_b
    shared_places=places_a & places_b
    try:
        ta=datetime.fromisoformat(a['published'].replace('Z','+00:00'))
        tb=datetime.fromisoformat(b['published'].replace('Z','+00:00'))
        close_in_time=abs((ta-tb).total_seconds())/3600 <= MAX_EVENT_AGE_HOURS
    except Exception:
        close_in_time=True
    if not close_in_time:
        return 0

    # Topic alone is never enough. "Energy", "security" or "elections"
    # can describe many unrelated events on the same day.
    if title_overlap>=.58:
        return .95
    if body_overlap>=.68 and shared_places:
        return .92
    if shared_places and shared_groups and title_overlap>=.22:
        return .88
    if shared_places and shared_groups and body_overlap>=.45:
        return .84
    return 0

def cluster_events(items):
    clusters=[]
    for item in sorted(items,key=lambda value:value.get('published',''),reverse=True):
        match=None; best=0
        for cluster in clusters:
            score=max(event_similarity(item,member) for member in cluster['members'])
            if score>best:
                best=score; match=cluster
        if match is not None and best>=.74:
            match['members'].append(item)
        else:
            clusters.append({'members':[item]})

    output=[]
    for index,cluster in enumerate(clusters,1):
        members=cluster['members']
        primary=members[0]
        sources=[]
        for member in members:
            source=member.get('source','')
            if source and source not in sources: sources.append(source)
        primary=dict(primary)
        primary['event_id']=f"evt-{primary.get('section','').lower().replace('ç','c')}-{index:03d}"
        primary['cluster_size']=len(members)
        primary['source_count']=len(sources)
        primary['sources']=sources
        primary['primary_source']=primary.get('source')
        primary['status']='today' if primary.get('within_24h') else 'update'
        if len(members)>1:
            confirmations=[]
            for member in members[1:3]:
                confirmations.append({
                    'source':member.get('source'),
                    'title':member.get('title'),
                    'link':member.get('link')
                })
            primary['confirmations']=confirmations
        output.append(primary)
    return output

def add(destination,seen,items):
    for item in sorted(items,key=lambda value:value['published'],reverse=True):
        if item['title'] and not exact_duplicate(item,seen):
            seen.append(item)
            destination.append(item)

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
        title=clean(entry.get('title')); summary=informative_summary(entry); published=published_at(entry)
        if pt:title=localize_pt(title); summary=localize_pt(summary)
        if not title or len(summary)<40 or not published or published>now or age_hours(published)>hours: continue
        if not relevant(section,title,summary) or not language_ok(title,summary,pt): continue
        link=entry.get('link','').strip()
        if not link.startswith(('http://','https://')) or 'news.google.com' in link.lower(): continue
        why,impact=context(section,title,f'{title} {summary}',pt)
        output.append({'section':section,'tags':tags(f'{title} {summary}'),'title':title,'summary':summary[:1100],'why':why,'impact':impact,'source':source,'published':published.isoformat(),'age_hours':round(max(0,age_hours(published)),1),'within_24h':age_hours(published)<=24,'link':link,'original_source':True})
    return output
def add(destination,seen,items):
    for item in sorted(items,key=lambda value:value['published'],reverse=True):
        if item['title'] and not duplicate(item,seen): seen.append(item); destination.append(item)
def build(language):
    pt=language=='pt'
    feeds=RSS_PT if pt else RSS_EN
    grouped={section:[] for section in MIN_TARGET}
    seen=[]

    # 1) Discovery: alerts/RSS are inputs, never the published unit.
    for section in MIN_TARGET:
        for source,url in feeds[section]:
            try:
                add(grouped[section],seen,parse(url,section,source,PRIMARY_HOURS,pt))
            except Exception as error:
                print('feed',source,section,type(error).__name__,str(error)[:160])

    # 2) Only use a short fallback window when a section has very little fresh material.
    #    Fallback items are explicitly marked as updates; they are not presented as "today".
    for section in MIN_TARGET:
        if len(grouped[section]) < 3:
            for source,url in feeds[section]:
                try:
                    add(grouped[section],seen,parse(url,section,source,FALLBACK_HOURS,pt))
                except Exception as error:
                    print('fallback',source,section,type(error).__name__,str(error)[:160])

    # 3) Cluster multiple alerts/sources that describe the same event.
    for section in grouped:
        grouped[section]=cluster_events(grouped[section])

    selected=[]
    for section,amount in DESIRED_TARGET.items():
        candidates=sorted(grouped[section],key=lambda value:(value.get('within_24h',False),value.get('published','')),reverse=True)
        chosen=[]; counts={}
        for item in candidates:
            source=item.get('source','')
            if counts.get(source,0)>=MAX_PER_SOURCE: continue
            chosen.append(item)
            counts[source]=counts.get(source,0)+1
            if len(chosen)==amount: break

        # Never invent volume just to fill a quota.
        distinct_sources={item.get('source') for item in chosen if item.get('source')}
        if language=='pt' and len(chosen)>=2 and len(distinct_sources)<2:
            chosen=chosen[:1]
        selected.extend(chosen)

    selected=sorted(selected,key=lambda value:value.get('published',''),reverse=True)

    # 4) Enrich only selected events.
    for item in selected:
        enriched=article_summary(item['link'],item['summary'],pt)
        if len(enriched)>len(item['summary']):
            if pt: enriched=localize_pt(enriched)
            item['summary']=enriched
            item['tags']=tags(f"{item['title']} {enriched}")
            item['why'],item['impact']=context(item['section'],item['title'],f"{item['title']} {enriched}",pt)

    payload={
        'updated_at':datetime.now(timezone.utc).isoformat(),
        'language':language,
        'window_hours':PRIMARY_HOURS,
        'fallback_hours':FALLBACK_HOURS,
        'carry_forward_hours':CARRY_FORWARD_HOURS,
        'items':selected,
        'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança','Tecnologia e IA'],
        'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'],
        'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento'],
        'generator':'GitHub Actions · Briefing Diário · Editorial Engine v2',
        'editorial_rule':'Alertas são descoberta; eventos agrupam fontes; só eventos seleccionados são publicados.',
        'section_counts':{section:sum(item['section']==section for item in selected) for section in MIN_TARGET}
    }
    return payload

if __name__ == '__main__':
    pt=build('pt'); en=build('en')
    Path('docs/news-pt.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('docs/news-en.json').write_text(json.dumps(en,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PT',pt['section_counts'],len(pt['items']),'EN',en['section_counts'],len(en['items']))
