import json, re, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

MIN_TARGET={'Moçambique':0,'África':0,'Mundo':0}
MAX_TARGET={'Moçambique':5,'África':5,'Mundo':5}
MIN_NEWS=0
STOPWORDS=set('a o as os de da do das dos e em no na nos nas por para com sem sobre entre que uma um uns umas ao aos à às se é foi são será após mais menos como seu sua seus suas the and of to for with from are is has have will after over into says new'.split())
PLACE_MARKERS=('mocambique','maputo','cabo delgado','tigray','etiopia','marrocos','angola','tanzania','malawi','zambia','zimbabwe','quenia','nigeria','ghana','congo','ruanda','uganda','somalia','sudao','egipto','namibia','botswana','arabia saudita','medio oriente','estados unidos','eua','portugal','franca','paris')
EVENT_GROUPS={'eleições':('eleicao','eleicoes','eleitoral','eleitorais','parlamento','partido'),'conflito':('guerra','conflito','rebeldes','forcas','armados','terrorismo','ataque'),'energia':('energia','energetico','combustivel','petroleo','gas','lng','electricidade','electrificacao'),'economia':('economia','investimento','inflacao','mercado','comercio','financiamento'),'tecnologia':('tecnologia','digital','inteligencia artificial','ia','telecomunicacoes')}
SOURCE_SCORE={
    'RTP Notícias':5,'RTP':5,'DW Português':5,'DW English':5,
    'BBC World':5,'BBC Africa':5,'BBC':5,'Al Jazeera English':5,
    'Club of Mozambique':4,'Diário Económico':4,'O País':4,'AIM News':4,'AIM Notícias':4,'Notícias ONU':5,
    'Jornal Notícias':4,'Checka':4,'Le Monde':4,'Reuters':5,'Associated Press':5
}
BAD_WORDS=('futebol','football','cinema','filme','música','music','novela','horóscopo','horoscope','moda','fashion','entretenimento','entertainment','hollywood','walk of fame','passeio da fama')
EN_MARKERS=(' the ',' and ',' of ',' to ',' for ',' with ',' from ',' are ',' is ',' has ',' have ',' will ',' after ',' over ')
PT_MARKERS=(' de ',' da ',' do ',' das ',' dos ',' para ',' com ',' que ',' uma ',' um ',' foi ',' será ',' estão ',' sobre ',' após ',' entre ')

def norm(s):
    s=unicodedata.normalize('NFKD',s.lower()).encode('ascii','ignore').decode()
    s=re.sub(r'[^a-z0-9 ]','',s)
    return re.sub(r'\s+',' ',s).strip()

def source_score(s):
    for k,v in SOURCE_SCORE.items():
        if k.lower() in s.lower(): return v
    return 2

def recency_score(x):
    h=max(0,float(x.get('age_hours',999)))
    return max(0,24-h)/24*5 if h<=24 else max(0,72-h)/48*1.5

def relevance_score(x):
    text=(x.get('title','')+' '+x.get('summary','')).lower(); score=0
    for w in ('lng','gás','gas','energy','energia','oil','econom','investment','investimento','business','trade','technology','tecnologia','artificial intelligence','security','segurança','war','guerra','diplomacy','diplomacia','infrastructure','infraestrutura','jobs','employment','emprego','mining','mineração'):
        if w in text: score+=1
    if x.get('section')=='Moçambique' and any(w in text for w in ('moçambique','mozambique','maputo','cabo delgado','pemba')): score+=3
    elif x.get('section')=='África' and any(w in text for w in ('africa','afric','angola','tanzania','tanzânia','south africa','áfrica do sul')): score+=2
    return min(score,8)

def valid(x,lang):
    title=x.get('title','').strip(); summary=x.get('summary','').strip(); link=x.get('link','').strip(); source=x.get('source','').strip()
    minimum_summary=120 if lang=='pt' else 100
    if len(title)<25 or len(title)>220 or len(summary)<minimum_summary or not link or not source: return False
    if any(w in (title+' '+summary).lower() for w in BAD_WORDS): return False
    if not link.startswith(('http://','https://')) or 'news.google.com' in link.lower(): return False
    if x.get('original_source') is not True: return False
    if x.get('carried_forward'): return False
    if x.get('status') == 'context': return False
    text=f" {title} {summary} ".lower()
    en_score=sum(marker in text for marker in EN_MARKERS); pt_score=sum(marker in text for marker in PT_MARKERS)
    if lang=='pt' and not (pt_score>=2 and pt_score>=en_score): return False
    if lang=='en' and not (en_score>=2 and en_score>=pt_score): return False
    try:
        d=datetime.fromisoformat(x['published'].replace('Z','+00:00'))
        if d>datetime.now(timezone.utc): return False
    except: return False
    return bool(x.get('why')) and bool(x.get('impact'))

def event_key(x):
    title=norm(x.get('title',''))
    places={p for p in PLACE_MARKERS if p in norm(x.get('title','')+' '+x.get('summary',''))}
    groups={g for g,s in EVENT_GROUPS.items() if any(v in norm(x.get('title','')+' '+x.get('summary','')) for v in s)}
    return title,places,groups

def dedupe(items):
    out=[]
    seen_events={}
    for x in sorted(items,key=lambda z:z.get('published',''),reverse=True):
        a=norm(x.get('title',''))
        if not a: continue
        title,places,groups=event_key(x)
        duplicate=False
        for y in out:
            b=norm(y.get('title','')); _,yp,yg=event_key(y)
            title_tokens={w for w in title.split() if len(w)>=4 and w not in STOPWORDS}
            other_tokens={w for w in b.split() if len(w)>=4 and w not in STOPWORDS}
            overlap=len(title_tokens & other_tokens)/max(1,min(len(title_tokens),len(other_tokens)))
            body_a={w for w in norm(x.get('title','')+' '+x.get('summary','')).split() if len(w)>=4 and w not in STOPWORDS}
            body_b={w for w in norm(y.get('title','')+' '+y.get('summary','')).split() if len(w)>=4 and w not in STOPWORDS}
            body_overlap=len(body_a & body_b)/max(1,min(len(body_a),len(body_b)))
            shared_groups=groups & yg
            same_event=bool(places & yp) and bool(shared_groups) and overlap>=.25
            if a==b or SequenceMatcher(None,a,b).ratio()>=.82 or overlap>=.72 or body_overlap>=.75 or same_event:
                duplicate=True; break
        if duplicate: continue
        out.append(x)
    return out

def editorial_context(x,lang):
    t=(x.get('title','')+' '+x.get('summary','')).lower(); sec=x.get('section')
    energy=any(w in t for w in ('lng','gás','gas','oil','energy','energia'))
    tech=any(w in t for w in ('artificial intelligence','inteligência artificial','technology','tecnologia'))
    security=any(w in t for w in ('war','guerra','conflict','conflito','security','segurança','military','militar','sanction','sanções','diplomacy','diplomacia'))
    economy=any(w in t for w in ('econom','investment','investimento','business','trade','comércio','comercio','market','mercado','inflation','inflação','employment','emprego','mining','mineração'))
    if lang=='en':
        if energy:
            return ('Energy and investment are strategic issues that can influence government and business decisions in the region.','It may affect energy prices, investment decisions, suppliers and supply chains.')
        if tech:
            return ('Technology is reshaping productivity, regulation and business models.','It may create demand for digital skills and new business opportunities while increasing pressure to adapt to regulation.')
        if security:
            if sec in ('Africa','Moçambique'):
                return ('Developments in security and diplomacy can change risk levels and decisions across the region.','It may affect trade, movement, supply chains, investment and perceptions of risk.')
            return ('The development has geopolitical relevance and may change risk, trade and investment decisions.','It may affect prices, supply chains, trade and investor risk perceptions.')
        if economy:
            if sec=='Moçambique':
                return ('The story helps track economic conditions that may influence businesses and households in Mozambique.','It may affect prices, demand, access to capital, hiring and opportunities for local suppliers.')
            if sec=='África':
                return ('The story helps explain economic and trade trends relevant to Africa.','It may affect regional trade, investment, employment, prices and opportunities for African businesses.')
            return ('The story helps track the direction of the global economy and investment decisions.','It may affect prices, access to capital, demand, suppliers and business opportunities.')
        return ('The story is worth following because of its potential economic, institutional or regional relevance.','Its concrete effect will depend on what happens next, but it may influence costs, business decisions or local opportunities.')
    if energy:
        return ('Energia e investimento são temas estratégicos que podem influenciar decisões de governos e empresas na região.','Pode afectar preços de energia, decisões de investimento, fornecedores e cadeias de abastecimento.')
    if tech:
        return ('A tecnologia está a transformar produtividade, regulação e modelos de negócio.','Pode criar procura por competências digitais e novas oportunidades, ao mesmo tempo que aumenta a pressão para adaptação e regulação.')
    if security:
        if sec in ('África','Moçambique'):
            return ('A evolução da segurança e da diplomacia pode alterar riscos e decisões na região.','Pode afectar comércio, circulação, cadeias de abastecimento, investimento e percepção de risco.')
        return ('A evolução tem relevância geopolítica e pode alterar riscos, comércio e decisões de investimento.','Pode afectar preços, cadeias de abastecimento, comércio e percepção de risco para investidores.')
    if economy:
        if sec=='Moçambique':
            return ('A notícia ajuda a acompanhar condições económicas que podem influenciar empresas e famílias em Moçambique.','Pode reflectir-se em preços, procura, acesso a capital, contratação e oportunidades para fornecedores locais.')
        if sec=='África':
            return ('A notícia ajuda a perceber tendências económicas e comerciais relevantes para África.','Pode afectar comércio regional, investimento, emprego, preços e oportunidades para empresas africanas.')
        return ('A notícia ajuda a acompanhar a direcção da economia global e das decisões de investimento.','Pode reflectir-se em preços, acesso a capital, procura, fornecedores e oportunidades de negócio.')
    return ('A notícia merece acompanhamento pelo potencial efeito económico, institucional ou regional.','O efeito concreto dependerá da evolução dos próximos dias, mas pode afectar custos, decisões empresariais ou oportunidades locais.')

def detailed_summary(x):
    parts=[x.get('summary','').strip(),x.get('why','').strip(),x.get('impact','').strip()]
    output=[]; seen=set()
    for part in parts:
        key=norm(part)
        if part and key not in seen:seen.add(key); output.append(part if part.endswith(('.','!','?','…')) else part+'.')
    return ' '.join(output)

def curate(d):
    lang=d.get('language','pt')
    items=dedupe([x for x in d.get('items',[]) if valid(x,lang)])

    for x in items:
        if not x.get('why') or not x.get('impact'):
            x['why'],x['impact']=editorial_context(x,lang)

        # A real opportunity must be evidenced by the story; do not manufacture one.
        text_value=norm(x.get('title','')+' '+x.get('summary',''))
        opportunity_terms=('contract','contrato','tender','procurement','invest','investment','investimento','project','projecto','jobs','employment','emprego','supplier','fornecedor','financing','financiamento','partnership','parceria')
        x['opportunity_flag']=any(term in text_value for term in opportunity_terms)

        x['detailed_summary']=detailed_summary(x)
        x['editorial_score']=round(
            source_score(x.get('source','')) +
            recency_score(x) +
            relevance_score(x) +
            (1.5 if x.get('source_count',1)>=2 else 0) +
            (1 if x.get('within_24h') else 0),
            2
        )
        x['source_tier']='A' if source_score(x.get('source',''))>=5 else ('B' if source_score(x.get('source',''))>=4 else 'C')
        x['editorial_status']='HOJE' if x.get('within_24h') else 'ACTUALIZAÇÃO'

    selected=[]
    for section,n in MAX_TARGET.items():
        choices=[x for x in items if x.get('section')==section]
        choices.sort(key=lambda x:x['editorial_score'],reverse=True)
        selected.extend(choices[:n])

    selected=sorted(selected,key=lambda x:x['editorial_score'],reverse=True)

    d['items']=selected
    d['section_counts']={s:sum(x.get('section')==s for x in selected) for s in MIN_TARGET}
    d['editorial']='Curadoria automática v2: descoberta → agrupamento de eventos → cruzamento de fontes → selecção por relevância. Não existe quota mínima de notícias.'
    d['briefing_intro']={
        'pt':'Bom dia. Este é o Briefing Diário. O foco de hoje é o que realmente mudou, por que importa e o que pode significar para Moçambique.',
        'en':'Good morning. This is the Daily Briefing. The focus is what actually changed, why it matters and what it may mean for Mozambique.'
    }
    return d

if __name__=='__main__':
    for name in ('news-pt.json','news-en.json'):
        p=Path('docs')/name; d=json.loads(p.read_text(encoding='utf-8')); curate(d); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    pt=json.loads(Path('docs/news-pt.json').read_text(encoding='utf-8')); Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8'); print('Editorial OK:',pt['section_counts'],len(pt['items']))
