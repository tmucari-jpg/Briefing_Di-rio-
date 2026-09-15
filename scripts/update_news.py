import json, re, unicodedata
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
RSS_PT={'Mundo':[('BBC Português','https://feeds.bbci.co.uk/portuguese/international/rss.xml')],'África':[('BBC Português','https://feeds.bbci.co.uk/portuguese/topics/africa/rss.xml')],'Moçambique':[('O País','https://opais.co.mz/feed/'),('Club of Mozambique','https://clubofmozambique.com/feed/')]}
RSS_EN={'Mundo':[('BBC World','https://feeds.bbci.co.uk/news/world/rss.xml')],'África':[('BBC Africa','https://feeds.bbci.co.uk/news/world/africa/rss.xml')],'Moçambique':[('Club of Mozambique','https://clubofmozambique.com/feed/')]}
THEMES=['energy','energia','lng','gas','oil','petróleo','petroleo','econom','economia','investment','investimento','business','negócios','trade','market','artificial intelligence','inteligência artificial','technology','tecnologia','security','segurança','conflict','conflito','war','guerra','military','sanction','sanções','infrastructure','infraestrutura','jobs','emprego','mining','mineração','climate','drought','flood','water','água','interest rate','inflation']
GLOBAL=['china','united states','u.s.','usa','europe','european union','russia','ukraine','middle east','israel','iran','saudi','yemen','india','japan','south korea','nato','opec','world bank','imf',' un ']
AFRICA=['africa','african','mozambique','moçambique','south africa','angola','tanzania','malawi','zambia','zimbabwe','kenya','nigeria','ghana','ethiopia','congo','rwanda','uganda','somalia','sudan','egypt','algeria','morocco','senegal','namibia','botswana','djibouti']
MOZ=['mozambique','moçambique','maputo','cabo delgado','pemba','niassa','nampula','beira','nacala','tete','inhambane','gaza','manica','zambezia','rovuma']
BAD=['emmy','celebrity','futebol','football','sport','sports','cinema','filme','movie','novela','música','music','horóscopo','horoscope','receita','recipe','estupro','rape','moda','fashion','reality show','influencer','casamento','namoro','documentário','documentary','entretenimento','entertainment','turtles','turtle','half-marathon','flooding interrupts']
EN_WORDS=['the ',' and ',' of ',' to ',' for ',' with ',' says ',' as ',' from ',' on ',' in ',' is ',' are ',' ai regulation ',' africa\'s ']
def clean(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s or '')).strip()
def norm(s): return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s.lower()).encode('ascii','ignore').decode())
def dt(item):
 for k in ('published_parsed','updated_parsed'):
  v=item.get(k)
  if v:
   try:return datetime(*v[:6],tzinfo=timezone.utc)
   except:pass
 for k in ('published','updated'):
  try:
   x=parsedate_to_datetime(item.get(k,''));return x.astimezone(timezone.utc) if x.tzinfo else x.replace(tzinfo=timezone.utc)
  except:pass
 return None
def age(d):return (datetime.now(timezone.utc)-d).total_seconds()/3600 if d else 99999
def likely_portuguese(title,desc): return not any(x in (' '+title+' '+desc).lower() for x in EN_WORDS)
def relevant(sec,title,desc):
 t=(title+' '+desc).lower()
 if any(x in t for x in BAD) or not any(x in t for x in THEMES):return False
 if sec=='Mundo':return any(x in t for x in GLOBAL) or any(x in t for x in ['lng','gas','oil','energy','artificial intelligence','war','guerra','sanction','tariff','interest rate','inflation'])
 if sec=='África':return any(x in t for x in AFRICA)
 return any(x in t for x in MOZ)
def tags(t):
 t=t.lower();o=[]
 if any(x in t for x in ['energy','energia','lng','gas','oil','petróleo','petroleo']):o.append('Energia')
 if any(x in t for x in ['artificial intelligence','inteligência artificial','technology','tecnologia']):o.append('IA')
 if any(x in t for x in ['econom','investment','investimento','business','negócios','trade','market']):o.append('Economia')
 if any(x in t for x in ['security','segurança','conflict','conflito','war','guerra','military','sanction']):o.append('Segurança')
 return o or ['Economia']
def context(sec,t):
 t=t.lower()
 if any(x in t for x in ['lng','gas','oil','energy','energia']): return 'Energia e investimento são temas estratégicos para a região e podem alterar decisões de empresas e governos.','Pode influenciar investimento, custos de energia, fornecedores locais e receitas ligadas ao setor energético.'
 if any(x in t for x in ['artificial intelligence','inteligência artificial','technology','tecnologia']): return 'A evolução tecnológica está a mudar produtividade, regulação e modelos de negócio.','Pode criar procura por competências digitais e novas oportunidades, mas também aumentar a pressão por adaptação e regulação.'
 if any(x in t for x in ['war','guerra','conflict','conflito','security','segurança','military','sanction']): return 'A evolução tem relevância geopolítica e pode alterar riscos, comércio e decisões de investimento.','Pode afetar preços, cadeias de abastecimento, comércio regional e perceção de risco para investidores.'
 if any(x in t for x in ['econom','investment','investimento','business','negócios','trade','market','inflation']): return 'A notícia ajuda a perceber a direção da economia e das decisões de investimento.','Pode refletir-se em preços, acesso a capital, procura por fornecedores e oportunidades de negócio.'
 return 'A notícia merece acompanhamento pelo potencial efeito económico, institucional ou regional.','O efeito concreto dependerá da evolução dos próximos dias, mas pode afetar custos, decisões empresariais ou oportunidades locais.'
def parse(url,sec,source,hours,pt=True):
 r=urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/10'}),timeout=25);f=feedparser.parse(r.read());out=[]
 for i in f.entries:
  title,desc=clean(i.get('title')),clean(i.get('summary') or i.get('description'));d=dt(i)
  if not title or not d or age(d)>hours or not relevant(sec,title,desc):continue
  if pt and not likely_portuguese(title,desc):continue
  w,im=context(sec,title+' '+desc)
  out.append({'section':sec,'tags':tags(title+' '+desc),'title':title,'summary':desc[:700],'why':w,'impact':im,'source':source,'published':d.isoformat(),'age_hours':round(age(d),1),'within_24h':age(d)<=24,'link':i.get('link','')})
 return out
def google(sec,q,hours,pt=True):
 cfg={'hl':'pt-PT','gl':'MZ','ceid':'MZ:pt-PT'} if pt else {'hl':'en-US','gl':'US','ceid':'US:en'}
 if hours>24:q=q.replace(' when:1d','')
 u='https://news.google.com/rss/search?'+urlencode({'q':q,'hl':cfg['hl'],'gl':cfg['gl'],'ceid':cfg['ceid']})
 return parse(u,sec,'Google News',hours,pt)
def add(dst,seen,items):
 for x in sorted(items,key=lambda z:z['published'],reverse=True):
  k=norm(x['title'])
  if k and k not in seen:seen.add(k);dst.append(x)
def build(lang):
 pt=lang=='pt';feeds=RSS_PT if pt else RSS_EN;by={s:[] for s in TARGET};seen=set()
 queries={'Mundo':['energia LNG geopolítica IA economia investimento quando:1d','economia global tecnologia conflito mercados quando:1d'],'África':['África energia investimento segurança economia tecnologia quando:1d','África LNG mineração comércio empregos quando:1d'],'Moçambique':['Moçambique LNG energia investimento economia empregos segurança quando:1d','Moçambique gás mineração infraestrutura negócios comércio quando:1d']}
 for s in TARGET:
  for src,u in feeds[s]:
   try:add(by[s],seen,parse(u,s,src,PRIMARY_HOURS,pt))
   except Exception:pass
  for q in queries[s]:
   try:add(by[s],seen,google(s,q,PRIMARY_HOURS,pt))
   except Exception:pass
 if sum(map(len,by.values()))<MIN_NEWS:
  for s in TARGET:
   for src,u in feeds[s]:
    try:add(by[s],seen,parse(u,s,src,FALLBACK_HOURS,pt))
    except Exception:pass
   for q in queries[s]:
    try:add(by[s],seen,google(s,q,FALLBACK_HOURS,pt))
    except Exception:pass
 selected=[]
 for s,n in TARGET.items():selected+=sorted(by[s],key=lambda x:x['published'],reverse=True)[:n]
 pool=sorted([x for s in by for x in by[s] if x not in selected],key=lambda x:x['published'],reverse=True);selected+=pool[:max(0,MIN_NEWS-len(selected))]
 if len(selected)<MIN_NEWS:raise SystemExit(f'Atualização {lang} insuficiente: {len(selected)} notícias.')
 selected=sorted(selected[:10],key=lambda x:x['published'],reverse=True)
 p={'updated_at':datetime.now(timezone.utc).isoformat(),'language':lang,'window_hours':24,'fallback_hours':72,'items':selected,'watch':['Energia e LNG','Economia e investimento','Geopolítica e segurança','Tecnologia e IA'],'risks':['Choques geopolíticos','Volatilidade económica','Risco de informação não verificada'],'opportunities':['Energia e fornecedores','Tecnologia e IA','Emprego, negócios e investimento'],'generator':'GitHub Actions · Briefing Diário','section_counts':{s:sum(x['section']==s for x in selected) for s in TARGET}}
 Path(f'docs/news-{lang}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');return p
pt=build('pt');en=build('en');Path('docs/news.json').write_text(json.dumps(pt,ensure_ascii=False,indent=2),encoding='utf-8');print('PT',len(pt['items']),pt['section_counts']);print('EN',len(en['items']),en['section_counts'])