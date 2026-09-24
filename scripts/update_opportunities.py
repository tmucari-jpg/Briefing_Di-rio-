import html, json, re, unicodedata
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import feedparser

DISCOVERY_DAYS=365
FRESH_WITHOUT_DEADLINE_DAYS=14
MAX_ITEMS=18
MAX_PER_SOURCE=6
SOURCES={
 'pt':[('Diário Económico — Concursos','https://www.diarioeconomico.co.mz/category/concursos-publicos/feed/'),('Diário Económico','https://www.diarioeconomico.co.mz/feed/'),('O País','https://opais.co.mz/feed/'),('Jornal Notícias','https://jornalnoticias.co.mz/feed/')],
 'en':[('Club of Mozambique','https://clubofmozambique.com/feed/'),('AIM News','https://aimnews.org/feed/'),('BBC Africa','https://feeds.bbci.co.uk/news/world/africa/rss.xml')],
}
EXXON_URL={'pt':'https://corporate.exxonmobil.com/locations/mozambique/expressions-of-interest?content-lang=pt','en':'https://corporate.exxonmobil.com/locations/mozambique/expressions-of-interest'}
MOZ=('moçambique','mozambique','maputo','matola','cabo delgado','pemba','nampula','nacala','tete','beira','inhambane','gaza','manica','zambézia','zambezia','niassa','rovuma','quelimane','afungi')
AFRICA=('africa','áfrica','african','angola','tanzania','tanzânia','south africa','áfrica do sul','malawi','zambia','zâmbia','zimbabwe','zimbabué','kenya','quénia','nigeria','nigéria','ghana','ethiopia','etiópia','congo','rwanda','ruanda','uganda','somalia','somália','sudan','sudão','egypt','egipto','morocco','marrocos','senegal','namibia','namíbia','botswana','eswatini','lesotho','cabo verde')
CATEGORIES={
 'Concursos':('concurso público','public tender','call for proposals','invitation to bid','request for proposal','request for quotation','licitação','concurso','tender','expression of interest','manifestação de interesse'),
 'Procurement':('procurement','supplier registration','supplier opportunity','fornecedor','fornecimento','aquisição de bens','aquisição de serviços'),
 'Financiamento':('call for applications','applications open','candidaturas abertas','grant programme','grant program','subvenção','fundo disponível','funding opportunity','linha de crédito'),
 'Empregos estratégicos':('vaga','vagas','vacancy','vacancies','recrutamento','recruitment','hiring','job opening'),
 'Expansão de empresas':('nova fábrica','new factory','new plant','entrada no mercado','market entry','abre filial','opens branch','expansão de operações','expansion of operations'),
 'Energia/LNG':('concessão','concession','licença de exploração','exploration licence','offtake agreement','power purchase agreement','project award','adjudicação'),
 'Tecnologia':('digital challenge','innovation challenge','aceleradora','accelerator programme','startup competition','tech grant','hackathon'),
 'Regulação & decretos':('entra em vigor','takes effect','novo regulamento','new regulation','novo decreto','new decree','licenciamento obrigatório','mandatory licensing'),
 'Novos projectos':('lança projecto','launches project','project approved','project awarded','construção aprovada','construction approved'),
 'Investimentos':('procura investidores','seeks investors','investment call','investment opportunity','parceria público-privada','public-private partnership'),
}
NEGATIVE=('dívida pública','public debt','massa salarial','wage bill','alerta','warning','opinião','opinion','editorial','eleições','elections','guerra','war','conflito','conflict','mortes','deaths','galeria','gallery','football','futebol')
MONTHS={'jan':1,'january':1,'janeiro':1,'feb':2,'february':2,'fevereiro':2,'mar':3,'march':3,'marco':3,'apr':4,'april':4,'abril':4,'may':5,'maio':5,'jun':6,'june':6,'junho':6,'jul':7,'july':7,'julho':7,'aug':8,'august':8,'agosto':8,'sep':9,'sept':9,'september':9,'setembro':9,'oct':10,'october':10,'outubro':10,'nov':11,'november':11,'novembro':11,'dec':12,'december':12,'dezembro':12}
EN_MARKERS=(' the ',' and ',' of ',' to ',' for ',' with ',' from ',' are ',' is ',' has ',' will ')
PT_MARKERS=(' de ',' da ',' do ',' das ',' dos ',' para ',' com ',' que ',' uma ',' um ',' foi ',' será ')

def clean(value):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value or ''))).strip()
def norm(value):
 value=unicodedata.normalize('NFKD',value.lower()).encode('ascii','ignore').decode()
 return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]',' ',value)).strip()
def language_ok(title,summary,language):
 text=f' {title} {summary} '.lower(); en=sum(x in text for x in EN_MARKERS); pt=sum(x in text for x in PT_MARKERS)
 return pt>=2 and pt>=en if language=='pt' else en>=2 and en>=pt
def published_at(item):
 for key in ('published_parsed','updated_parsed'):
  value=item.get(key)
  if value:
   try:return datetime(*value[:6],tzinfo=timezone.utc)
   except Exception:pass
 for key in ('published','updated'):
  try:
   value=parsedate_to_datetime(item.get(key,'')); return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
  except Exception:pass
 return None
def age_days(value):return (datetime.now(timezone.utc)-value).total_seconds()/86400 if value else 99999
def parse_date(value):
 if not value:return None
 raw=norm(value).replace(' de ',' ')
 match=re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b',raw)
 if match:
  day,month,year=map(int,match.groups()); year+=2000 if year<100 else 0
  try:return date(year,month,day)
  except ValueError:return None
 match=re.search(r'\b(\d{1,2})[ -]([a-z]+)[ -,]*(\d{2,4})?\b',raw)
 if match:
  day=int(match.group(1)); month=MONTHS.get(match.group(2),MONTHS.get(match.group(2)[:3])); year=int(match.group(3)) if match.group(3) else date.today().year; year+=2000 if year<100 else 0
  if month:
   try:return date(year,month,day)
   except ValueError:return None
 return None
def deadline_info(text,language):
 pattern=r'(?:prazo(?: de submissão)?|candidaturas até|submissões até|até|deadline(?: for submission)?|closes?|closing date)\s*[:\-]?\s*((?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(?:\d{1,2}\s+(?:de\s+)?[A-Za-zÀ-ÿ]+(?:\s+(?:de\s+)?\d{2,4})?))'
 match=re.search(pattern,text,re.I)
 if match:
  label=clean(match.group(1)); return label,parse_date(label)
 return ('Confirmar na fonte original' if language=='pt' else 'Confirm in the original source'),None
def region(text):
 text=text.lower()
 if any(x in text for x in MOZ):return 'Moçambique'
 if any(x in text for x in AFRICA):return 'África'
 return 'Mundo'
def category(text):
 text=text.lower()
 for name,signals in CATEGORIES.items():
  if any(x in text for x in signals):return name
 return None
def action(title,language):
 short=clean(title)[:120]
 return f'Abrir o anúncio original de «{short}», confirmar os requisitos e o prazo e preparar os documentos solicitados.' if language=='pt' else f'Open the original notice for “{short}”, confirm the requirements and deadline, and prepare the requested documents.'
def make_item(title,summary,source,published,link,language,fixed_deadline=None,entity=None):
 text=f'{title} {summary}'; name=category(text)
 if not name or any(x in text.lower() for x in NEGATIVE):return None
 if not link.startswith(('http://','https://')) or 'news.google.com' in link.lower():return None
 deadline_label,deadline_date=fixed_deadline or deadline_info(text,language)
 if deadline_date and deadline_date<datetime.now(timezone.utc).date():return None
 if not deadline_date and age_days(published)>FRESH_WITHOUT_DEADLINE_DAYS:return None
 location=region(text)
 if location=='Mundo' and source in ('Diário Económico — Concursos','Diário Económico','O País','Jornal Notícias','ExxonMobil Moçambique'):location='Moçambique'
 score=(5 if deadline_date else 2)+(4 if location=='Moçambique' else 2 if location=='África' else 1)+(3 if name in ('Concursos','Procurement','Financiamento','Empregos estratégicos') else 2)
 fallback='Confirmar na fonte original' if language=='pt' else 'Confirm in the original source'; short=clean(title)[:130]
 why=f'A oportunidade «{short}» tem entidade responsável, acção concreta e prazo que devem ser verificados antes da candidatura.' if language=='pt' else f'The “{short}” opportunity has a responsible entity, a concrete action and a deadline that should be checked before applying.'
 return {'section':location,'category':name,'title':title,'summary':summary[:650],'entity':entity or source,'deadline':deadline_label,'eligibility':fallback,'why':why,'action':action(title,language),'source':source,'published':published.isoformat(),'age_hours':round(max(0,age_days(published)*24),1),'link':link,'original_source':True,'verification_status':fallback,'actionability_score':score}
def parse_feed(source,url,language):
 request=Request(url,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/18','Accept':'application/rss+xml, application/xml, text/xml, */*'})
 with urlopen(request,timeout=25) as response:feed=feedparser.parse(response.read())
 output=[]
 for entry in feed.entries:
  title=clean(entry.get('title')); summary=clean(entry.get('summary') or entry.get('description')); published=published_at(entry)
  if not title or len(summary)<40 or not published or age_days(published)<0 or age_days(published)>DISCOVERY_DAYS:continue
  if not language_ok(title,summary,language):continue
  item=make_item(title,summary,source,published,entry.get('link','').strip(),language)
  if item:output.append(item)
 return output

class TableParser(HTMLParser):
 def __init__(self):super().__init__(); self.rows=[]; self.row=None; self.cell=None; self.href=''
 def handle_starttag(self,tag,attrs):
  if tag=='tr':self.row=[]
  elif tag in ('td','th') and self.row is not None:self.cell=[]
  elif tag=='a' and self.cell is not None:self.href=dict(attrs).get('href','')
 def handle_data(self,data):
  if self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag in ('td','th') and self.cell is not None:self.row.append((clean(' '.join(self.cell)),self.href)); self.cell=None; self.href=''
  elif tag=='tr' and self.row is not None:
   if self.row:self.rows.append(self.row)
   self.row=None
def parse_exxon(language):
 url=EXXON_URL[language]; request=Request(url,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/18'})
 with urlopen(request,timeout=30) as response:body=response.read().decode('utf-8','ignore')
 parser=TableParser(); parser.feed(body); output=[]
 for row in parser.rows:
  if len(row)<4:continue
  title,href=row[0]; entity=row[1][0]; release_label=row[2][0]; closing_label=row[3][0]; release_date=parse_date(release_label); closing_date=parse_date(closing_label)
  if not title or not release_date or not closing_date or closing_date<datetime.now(timezone.utc).date():continue
  published=datetime(release_date.year,release_date.month,release_date.day,tzinfo=timezone.utc)
  summary=(f'{entity} convida empresas qualificadas para «{title}». O prazo indicado na fonte oficial termina em {closing_label}. Manifestação de interesse.' if language=='pt' else f'{entity} invites qualified companies for “{title}”. The deadline shown in the official source is {closing_label}. Expression of interest.')
  item=make_item(title,summary,'ExxonMobil Moçambique',published,urljoin(url,href) if href else url,language,(closing_label,closing_date),entity)
  if item:output.append(item)
 return output
def duplicate(candidate,selected):
 title=norm(candidate['title']); words={x for x in title.split() if len(x)>=4}
 for item in selected:
  other=norm(item['title']); other_words={x for x in other.split() if len(x)>=4}; overlap=len(words & other_words)/max(1,min(len(words),len(other_words)))
  if SequenceMatcher(None,title,other).ratio()>=.70 or overlap>=.65:return True
 return False
def build(language):
 items=[]
 try:items.extend(parse_exxon(language))
 except Exception as error:print('direct ExxonMobil',type(error).__name__,str(error)[:160])
 for source,url in SOURCES[language]:
  try:items.extend(parse_feed(source,url,language))
  except Exception as error:print('feed',source,type(error).__name__,str(error)[:160])
 items.sort(key=lambda x:(x['actionability_score'],-x['age_hours']),reverse=True); selected=[]; counts={}
 for item in items:
  if counts.get(item['source'],0)>=MAX_PER_SOURCE or duplicate(item,selected):continue
  selected.append(item); counts[item['source']]=counts.get(item['source'],0)+1
  if len(selected)==MAX_ITEMS:break
 selected.sort(key=lambda x:x['published'],reverse=True)
 return {'updated_at':datetime.now(timezone.utc).isoformat(),'language':language,'discovery_days':DISCOVERY_DAYS,'fresh_without_deadline_days':FRESH_WITHOUT_DEADLINE_DAYS,'items':selected,'categories':list(CATEGORIES),'note':'Radar editorial: oportunidades com prazo identificado permanecem visíveis até à data-limite; anúncios sem prazo ficam visíveis apenas durante 14 dias.' if language=='pt' else 'Editorial radar: opportunities with an identified deadline remain visible until that date; notices without a deadline remain visible for 14 days only.','generator':'GitHub Actions · Radar de Oportunidades'}

if __name__=='__main__':
 Path('docs/opportunities-pt.json').write_text(json.dumps(build('pt'),ensure_ascii=False,indent=2),encoding='utf-8')
 Path('docs/opportunities-en.json').write_text(json.dumps(build('en'),ensure_ascii=False,indent=2),encoding='utf-8')
 print('Radar de oportunidades actualizado.')
