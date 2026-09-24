import html, json, re, shutil, subprocess, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

import feedparser

PRIMARY_HOURS = 24
FALLBACK_HOURS = 168
TARGET = {'Moçambique': 4, 'África': 3, 'Mundo': 3}
MAX_PER_SOURCE = 2
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
EN_WORDS = [' the ',' and ',' of ',' to ',' for ',' with ',' says ',' from ',' are ',' is ',' africa\'s ']

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
    score=sum(marker in f' {title} {summary} '.lower() for marker in EN_WORDS)
    return score<2 if pt else score>=2
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
def context(section,text):
    text=text.lower()
    if any(x in text for x in ['lng','gás','gas','oil','energy','energia','fuel','combustível']):
        if section=='Moçambique': return 'O tema pode ter ligação directa com a posição de Moçambique no sector energético e com decisões de investimento na região.','Pode afectar projectos, fornecedores locais, custos de energia, receitas e oportunidades de negócio.'
        return 'Energia e investimento são temas estratégicos para a região e podem alterar decisões de empresas e governos.','Pode influenciar preços, investimento, fornecedores e cadeias de abastecimento.'
    if any(x in text for x in ['artificial intelligence','inteligência artificial','technology','tecnologia']): return 'A evolução tecnológica está a mudar a produtividade, a regulação e os modelos de negócio.','Pode criar procura por competências digitais e novas oportunidades, mas também aumentar a pressão por adaptação.'
    if any(x in text for x in ['war','guerra','conflict','conflito','security','segurança','sanction','sanções','diplomacia']): return 'A evolução da segurança e da diplomacia pode alterar riscos e decisões.','Pode afectar o comércio, a circulação, as cadeias de abastecimento, o investimento e a percepção de risco.'
    if any(x in text for x in ['econom','investment','investimento','business','trade','comércio','market','inflation','emprego']): return 'A notícia ajuda a acompanhar condições económicas e comerciais relevantes.','Pode reflectir-se em preços, procura, acesso a capital, contratação e oportunidades para fornecedores.'
    return 'A notícia merece acompanhamento pelo potencial efeito económico, institucional ou regional.','O efeito concreto dependerá da evolução dos próximos dias, mas pode afectar custos, decisões empresariais ou oportunidades locais.'
def duplicate(key,seen):
    for other in seen:
        left,right=set(key.split()),set(other.split())
        overlap=len(left & right)/max(1,min(len(left),len(right)))
        if key==other or SequenceMatcher(None,key,other).ratio()>=.82 or overlap>=.80: return True
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
        why,impact=context(section,f'{title} {summary}')
        output.append({'section':section,'tags':tags(f'{title} {summary}'),'title':title,'summary':summary[:700],'why':why,'impact':impact,'source':source,'published':published.isoformat(),'age_hours':round(max(0,age_hours(published)),1),'within_24h':age_hours(published)<=24,'link':link,'original_source':True})
    return output
def add(destination,seen,items):
    for item in sorted(items,key=lambda value:value['published'],reverse=True):
        key=norm(item['title'])
        if key and not duplicate(key,seen): seen.add(key); destination.append(item)
def build(language):
    pt=language=='pt'; feeds=RSS_PT if pt else RSS_EN; grouped={section:[] for section in TARGET}; seen=set()
    for section in TARGET:
        for source,url in feeds[section]:
            try: add(grouped[section],seen,parse(url,section,source,PRIMARY_HOURS,pt))
            except Exception as error: print('feed',source,section,type(error).__name__,str(error)[:160])
    if any(len(grouped[section])<TARGET[section] for section in TARGET):
        for section in TARGET:
            for source,url in feeds[section]:
                try: add(grouped[section],seen,parse(url,section,source,FALLBACK_HOURS,pt))
                except Exception as error: print('fallback',source,section,type(error).__name__,str(error)[:160])
    missing={section:TARGET[section]-len(grouped[section]) for section in TARGET if len(grouped[section])<TARGET[section]}
    if missing: raise SystemExit(f'Actualização {language} rejeitada: secções insuficientes {missing}.')
    selected=[]
    for section,amount in TARGET.items():
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
    payload={'updated_at':datetime.now(timezone.utc).isoformat(),'language':language,'window_hours':24,'fallback_hours':FALLBACK_HOURS,'items':selected,'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança','Tecnologia e IA'],'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'],'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento'],'generator':'GitHub Actions · Briefing Diário','section_counts':{section:sum(item['section']==section for item in selected) for section in TARGET}}
    Path(f'docs/news-{language}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return payload

if __name__ == '__main__':
    pt=build('pt'); en=build('en')
    Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PT',pt['section_counts'],len(pt['items']),'EN',en['section_counts'],len(en['items']))
