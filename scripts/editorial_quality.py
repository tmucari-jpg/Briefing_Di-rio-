import json, re, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

MIN_TARGET={'Moçambique':4,'África':3,'Mundo':3}
MAX_TARGET={'Moçambique':6,'África':6,'Mundo':6}
MIN_NEWS=10
STOPWORDS=set('a o as os de da do das dos e em no na nos nas por para com sem sobre entre que uma um uns umas ao aos à às se é foi são será após mais menos como seu sua seus suas the and of to for with from are is has have will after over into says new'.split())
SOURCE_SCORE={
    'RTP Notícias':5,'RTP':5,'DW Português':5,'DW English':5,
    'BBC World':5,'BBC Africa':5,'BBC':5,'Al Jazeera English':5,
    'Club of Mozambique':4,'Diário Económico':4,'O País':4,'AIM News':4,
    'Jornal Notícias':4,'Checka':4,'Le Monde':4,'Reuters':5,'Associated Press':5
}
BAD_WORDS=('futebol','football','cinema','filme','música','music','novela','horóscopo','horoscope','moda','fashion','entretenimento','entertainment')
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
    if len(title)<25 or len(title)>220 or len(summary)<40 or not link or not source: return False
    if any(w in (title+' '+summary).lower() for w in BAD_WORDS): return False
    if not link.startswith(('http://','https://')) or 'news.google.com' in link.lower(): return False
    if x.get('original_source') is not True: return False
    text=f" {title} {summary} ".lower()
    en_score=sum(marker in text for marker in EN_MARKERS); pt_score=sum(marker in text for marker in PT_MARKERS)
    if lang=='pt' and not (pt_score>=2 and pt_score>=en_score): return False
    if lang=='en' and not (en_score>=2 and en_score>=pt_score): return False
    try:
        d=datetime.fromisoformat(x['published'].replace('Z','+00:00'))
        if d>datetime.now(timezone.utc): return False
    except: return False
    return bool(x.get('why')) and bool(x.get('impact'))

def dedupe(items):
    out=[]
    for x in sorted(items,key=lambda z:z.get('published',''),reverse=True):
        a=norm(x.get('title','')); at={w for w in a.split() if len(w)>=4 and w not in STOPWORDS}; ab={w for w in norm(x.get('title','')+' '+x.get('summary','')).split() if len(w)>=4 and w not in STOPWORDS}
        if not a: continue
        duplicate=False
        for y in out:
            b=norm(y.get('title','')); bt={w for w in b.split() if len(w)>=4 and w not in STOPWORDS}; bb={w for w in norm(y.get('title','')+' '+y.get('summary','')).split() if len(w)>=4 and w not in STOPWORDS}
            title_overlap=len(at & bt)/max(1,min(len(at),len(bt))); body_overlap=len(ab & bb)/max(1,min(len(ab),len(bb)))
            if a==b or SequenceMatcher(None,a,b).ratio()>=.70 or title_overlap>=.60 or body_overlap>=.68: duplicate=True; break
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

def curate(d):
    lang=d.get('language','pt')
    items=dedupe([x for x in d.get('items',[]) if valid(x,lang)])
    for x in items:
        if not x.get('why') or not x.get('impact'):
            x['why'],x['impact']=editorial_context(x,lang)
        x['editorial_score']=round(source_score(x.get('source',''))+recency_score(x)+relevance_score(x),2)
        x['source_tier']='A' if source_score(x.get('source',''))>=5 else ('B' if source_score(x.get('source',''))>=4 else 'C')
    items.sort(key=lambda x:x['editorial_score'],reverse=True)
    counts={s:0 for s in MIN_TARGET}; selected=[]
    for s,n in MAX_TARGET.items():
        choices=[x for x in items if x['section']==s]; selected.extend(choices[:n]); counts[s]=min(len(choices),n)
    if any(counts[s]<n for s,n in MIN_TARGET.items()): raise SystemExit(f'Qualidade editorial rejeitada: secções insuficientes {counts}.')
    selected=sorted(selected,key=lambda x:x['editorial_score'],reverse=True)
    if len(selected)<MIN_NEWS: raise SystemExit(f'Qualidade editorial rejeitada: apenas {len(selected)} notícias válidas.')
    d['items']=selected; d['section_counts']={s:sum(x['section']==s for x in selected) for s in MIN_TARGET}
    d['editorial']='Curadoria automática: relevância + actualidade + qualidade da fonte original + deduplicação + validação geográfica.'
    d['briefing_intro']={'pt':'Bom dia. Este é o Briefing Diário. Hoje, vale a pena acompanhar primeiro os temas com maior impacto potencial em geopolítica, economia, energia, tecnologia e Moçambique.','en':'Good morning. This is the Daily Briefing. Today, focus first on the stories with the strongest potential relevance to geopolitics, the economy, energy, technology and Mozambique.'}
    return d

if __name__=='__main__':
    for name in ('news-pt.json','news-en.json'):
        p=Path('docs')/name; d=json.loads(p.read_text(encoding='utf-8')); curate(d); p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    pt=json.loads(Path('docs/news-pt.json').read_text(encoding='utf-8')); Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8'); print('Editorial OK:',pt['section_counts'],len(pt['items']))
