import html, json, re, unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import feedparser

PRIMARY_HOURS=24
FALLBACK_HOURS=72
MIN_NEWS=8
TARGET={'Mundo':4,'África':2,'Moçambique':2}

RSS_PT={
 'Mundo':[
   ('RTP Notícias — Mundo','https://www.rtp.pt/noticias/rss/mundo'),
   ('RTP Notícias — Últimas','https://www.rtp.pt/noticias/rss')
 ],
 'África':[
   ('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html'),
   ('RTP Notícias — Mundo','https://www.rtp.pt/noticias/rss/mundo')
 ],
 'Moçambique':[
   ('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html'),
   ('RTP Notícias — Últimas','https://www.rtp.pt/noticias/rss')
 ]
}
RSS_EN={
 'Mundo':[('BBC World','https://feeds.bbci.co.uk/news/world/rss.xml')],
 'África':[('BBC Africa','https://feeds.bbci.co.uk/news/world/africa/rss.xml')],
 'Moçambique':[('Club of Mozambique','https://clubofmozambique.com/feed/')]
}

THEMES=[
 'energy','energia','lng','gás','gas','oil','petróleo','petroleo','econom','economia',
 'investment','investimento','business','negócios','negocios','trade','comércio','comercio',
 'market','mercado','artificial intelligence','inteligência artificial','technology','tecnologia',
 'security','segurança','conflito','conflict','war','guerra','military','militar','sanction','sanções',
 'infrastructure','infraestrutura','jobs','emprego','employment','mining','mineração','climate',
 'drought','flood','water','água','interest rate','inflation','inflação','tariff','tarifas',
 'election','eleição','eleições','governo','government','diplomacia','diplomacy','refugiados','refugees'
]
GLOBAL=['china','united states','europe','european union','russia','ukraine','middle east','israel','iran','saudi','yemen','india','japan','south korea','nato','opec','world bank','imf','onu','trump','putin']
AFRICA=['africa','africano','africana','africanos','africanas','moçambique','mozambique','áfrica do sul','south africa','angola','tanzânia','tanzania','malawi','zâmbia','zambia','zimbabué','zimbabwe','quénia','kenya','nigéria','nigeria','ghana','etiópia','ethiopia','congo','ruanda','rwanda','uganda','somália','somalia','sudão','sudan','egito','egypt','argélia','algeria','marrocos','morocco','senegal','namíbia','namibia','botswana','eswatini','lesoto','lesotho']
MOZ=['moçambique','mozambique','maputo','cabo delgado','cabo delgado province','pemba','niassa','nampula','beira','nacala','tete','inhambane','gaza','manica','zambézia','zambezia','rovuma','quelimane','matola']
BAD=['futebol','football','sport','sports','cinema','filme','movie','novela','música','music','horóscopo','horoscope','receita','recipe','moda','fashion','reality show','influencer','casamento','namoro','documentário','documentary','entretenimento','entertainment','turtles','turtle','half-marathon']
EN_WORDS=[' the ',' and ',' of ',' to ',' for ',' with ',' says ',' from ',' are ',' is ',' ai regulation ',' africa\'s ']

def clean(s):
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()

def norm(s):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s.lower()).encode('ascii','ignore').decode())

def dt(item):
    for k in ('published_parsed','updated_parsed'):
        v=item.get(k)
        if v:
            try:return datetime(*v[:6],tzinfo=timezone.utc)
            except:pass
    for k in ('published','updated'):
        try:
            x=parsedate_to_datetime(item.get(k,''))
            return x.astimezone(timezone.utc) if x.tzinfo else x.replace(tzinfo=timezone.utc)
        except:pass
    return None

def age(d):
    return (datetime.now(timezone.utc)-d).total_seconds()/3600 if d else 99999

def likely_portuguese(title,desc):
    text=(' '+title+' '+desc+' ').lower()
    return not any(x in text for x in EN_WORDS)

def relevant(sec,title,desc):
    t=(title+' '+desc).lower()
    if any(x in t for x in BAD): return False
    has_theme=any(x in t for x in THEMES)
    if not has_theme: return False
    if sec=='Mundo':
        return any(x in t for x in GLOBAL) or any(x in t for x in ['lng','gás','gas','energia','inteligência artificial','guerra','sanções','tarifas','inflação'])
    if sec=='África':
        return any(x in t for x in AFRICA)
    return any(x in t for x in MOZ)

def tags(t):
    t=t.lower(); o=[]
    if any(x in t for x in ['energy','energia','lng','gás','gas','oil','petróleo','petroleo']): o.append('Energia')
    if any(x in t for x in ['artificial intelligence','inteligência artificial','technology','tecnologia']): o.append('IA')
    if any(x in t for x in ['econom','investment','investimento','business','negócios','negocios','trade','comércio','comercio','market','mercado','inflation','inflação','employment','emprego']): o.append('Economia')
    if any(x in t for x in ['security','segurança','conflict','conflito','war','guerra','military','militar','sanction','sanções','diplomacia','diplomacy']): o.append('Segurança')
    return o or ['Economia']

def context(sec,t):
    t=t.lower()
    if any(x in t for x in ['lng','gás','gas','oil','energy','energia']):
        if sec=='Moçambique': return 'O tema pode ter ligação direta com a posição de Moçambique no setor energético e com decisões de investimento na região.','Pode afetar projetos de gás, fornecedores locais, custos de energia, receitas e oportunidades de negócio.'
        return 'Energia e investimento são temas estratégicos para a região e podem alterar decisões de empresas e governos.','Pode influenciar preços de energia, investimento, fornecedores e cadeias de abastecimento.'
    if any(x in t for x in ['artificial intelligence','inteligência artificial','technology','tecnologia']):
        return 'A evolução tecnológica está a mudar produtividade, regulação e modelos de negócio.','Pode criar procura por competências digitais e novas oportunidades, mas também aumentar a pressão por adaptação e regulação.'
    if any(x in t for x in ['war','guerra','conflict','conflito','security','segurança','military','militar','sanction','sanções','diplomacia','diplomacy']):
        if sec in ('África','Moçambique'): return 'A evolução da segurança e da diplomacia pode alterar riscos e decisões na região.','Pode afetar comércio, circulação, cadeias de abastecimento, investimento e perceção de risco.'
        return 'A evolução tem relevância geopolítica e pode alterar riscos, comércio e decisões de investimento.','Pode afetar preços, cadeias de abastecimento, comércio regional e perceção de risco para investidores.'
    if any(x in t for x in ['econom','investment','investimento','business','negócios','negocios','trade','comércio','comercio','market','mercado','inflation','inflação','employment','emprego']):
        if sec=='Moçambique': return 'A notícia ajuda a acompanhar condições económicas que podem influenciar empresas e famílias em Moçambique.','Pode refletir-se em preços, procura, acesso a capital, contratação e oportunidades para fornecedores locais.'
        if sec=='África': return 'A notícia ajuda a perceber tendências económicas e comerciais relevantes para a região.','Pode afetar comércio regional, investimento, emprego, preços e oportunidades para empresas africanas.'
        return 'A notícia ajuda a perceber a direção da economia e das decisões de investimento.','Pode refletir-se em preços, acesso a capital, procura por fornecedores e oportunidades de negócio.'
    return 'A notícia merece acompanhamento pelo potencial efeito económico, institucional ou regional.','O efeito concreto dependerá da evolução dos próximos dias, mas pode afetar custos, decisões empresariais ou oportunidades locais.'

def parse(url,sec,source,hours,pt=True):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/12','Accept':'application/rss+xml, application/xml, text/xml, */*'})
    with urlopen(req,timeout=30) as r: raw=r.read()
    f=feedparser.parse(raw); out=[]; now=datetime.now(timezone.utc)
    for i in f.entries:
        title,desc=clean(i.get('title')),clean(i.get('summary') or i.get('description')); d=dt(i)
        if not title or not d: continue
        # Evita publicar itens com data futura anómala do feed.
        if d>now.replace(microsecond=0): continue
        if age(d)>hours or not relevant(sec,title,desc): continue
        if pt and not likely_portuguese(title,desc): continue
        w,im=context(sec,title+' '+desc)
        actual_source=source
        try: actual_source=clean(i.get('source',{}).get('title') or source)
        except: pass
        out.append({'section':sec,'tags':tags(title+' '+desc),'title':title,'summary':desc[:700],'why':w,'impact':im,'source':actual_source,'published':d.isoformat(),'age_hours':round(max(0,age(d)),1),'within_24h':age(d)<=24,'link':i.get('link','')})
    return out

def google(sec,q,hours,pt=True):
    cfg={'hl':'pt-PT','gl':'MZ','ceid':'MZ:pt-PT'} if pt else {'hl':'en-US','gl':'US','ceid':'US:en'}
    u='https://news.google.com/rss/search?'+urlencode({'q':q,'hl':cfg['hl'],'gl':cfg['gl'],'ceid':cfg['ceid']})
    return parse(u,sec,'Google News',hours,pt)

def add(dst,seen,items):
    for x in sorted(items,key=lambda z:z['published'],reverse=True):
        k=norm(x['title'])
        if k and k not in seen:
            seen.add(k); dst.append(x)

def build(lang):
    pt=lang=='pt'; feeds=RSS_PT if pt else RSS_EN; by={s:[] for s in TARGET}; seen=set()
    queries={
      'Mundo':[
        'geopolítica OR guerra OR sanções OR energia OR LNG OR inteligência artificial economia investimento when:1d',
        'economia global OR tecnologia OR comércio OR mercados when:1d'
      ],
      'África':[
        '(África OR Angola OR Tanzânia OR África do Sul OR Quénia OR Nigéria OR Etiópia) (energia OR investimento OR economia OR segurança OR comércio OR tecnologia OR eleições) when:1d',
        '(África OR Angola OR Tanzânia OR África do Sul OR Malawi OR Zâmbia) (LNG OR gás OR mineração OR infraestrutura OR empregos OR diplomacia) when:1d'
      ],
      'Moçambique':[
        '(Moçambique OR Maputo OR Cabo Delgado OR Pemba OR Nampula OR Beira) (energia OR LNG OR gás OR investimento OR economia OR segurança OR empregos OR mineração OR infraestrutura) when:1d',
        '(Moçambique OR Mozambique) (comércio OR negócios OR tecnologia OR diplomacia OR governo OR empresas) when:1d'
      ]
    }
    for s in TARGET:
        for src,u in feeds[s]:
            try:add(by[s],seen,parse(u,s,src,PRIMARY_HOURS,pt))
            except Exception as e: print('feed',src,s,type(e).__name__,str(e)[:160])
        for q in queries[s]:
            try:add(by[s],seen,google(s,q,PRIMARY_HOURS,pt))
            except Exception as e: print('google',s,type(e).__name__,str(e)[:160])
    # Só usa 72h como fallback quando a janela de 24h não permite cumprir o mínimo.
    if any(len(by[s])<TARGET[s] for s in TARGET):
        for s in TARGET:
            if len(by[s])>=TARGET[s]: continue
            for src,u in feeds[s]:
                try:add(by[s],seen,parse(u,s,src,FALLBACK_HOURS,pt))
                except Exception as e: print('fallback feed',src,s,type(e).__name__,str(e)[:160])
            for q in queries[s]:
                try:add(by[s],seen,google(s,q,FALLBACK_HOURS,pt))
                except Exception as e: print('fallback google',s,type(e).__name__,str(e)[:160])
    # Regra crítica: nunca publicar 8 notícias de uma única região só para cumprir o total.
    missing={s:TARGET[s]-len(by[s]) for s in TARGET if len(by[s])<TARGET[s]}
    if missing: raise SystemExit(f'Atualização {lang} rejeitada: secções insuficientes {missing}. Não publicar briefing incompleto.')
    selected=[]
    for s,n in TARGET.items(): selected+=sorted(by[s],key=lambda x:x['published'],reverse=True)[:n]
    pool=sorted([x for s in by for x in by[s] if x not in selected],key=lambda x:x['published'],reverse=True)
    selected+=pool[:max(0,10-len(selected))]
    if len(selected)<MIN_NEWS: raise SystemExit(f'Atualização {lang} insuficiente: {len(selected)} notícias.')
    selected=sorted(selected[:10],key=lambda x:x['published'],reverse=True)
    p={'updated_at':datetime.now(timezone.utc).isoformat(),'language':lang,'window_hours':24,'fallback_hours':72,'items':selected,'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança','Tecnologia e IA'],'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'],'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento'],'generator':'GitHub Actions · Briefing Diário','section_counts':{s:sum(x['section']==s for x in selected) for s in TARGET}}
    Path(f'docs/news-{lang}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8'); return p

pt=build('pt'); en=build('en'); Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8'); print('PT',len(pt['items']),pt['section_counts']); print('EN',len(en['items']),en['section_counts'])
