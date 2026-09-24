import html, json, re, unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

import feedparser

WINDOW_HOURS=7*24
MAX_ITEMS=12
MAX_PER_SOURCE=5
SOURCES={
 'pt':[('Diário Económico — Concursos','https://www.diarioeconomico.co.mz/category/concursos-publicos/feed/'),('Diário Económico','https://www.diarioeconomico.co.mz/feed/'),('O País','https://opais.co.mz/feed/'),('Club of Mozambique','https://clubofmozambique.com/feed/'),('RTP Notícias — Mundo','https://www.rtp.pt/noticias/rss/mundo'),('DW Português','https://rss.dw.com/syndication/feeds/DW_para_A_Verdade.12133-cb.html')],
 'en':[('Club of Mozambique','https://clubofmozambique.com/feed/'),('AIM News','https://aimnews.org/feed/'),('BBC Africa','https://feeds.bbci.co.uk/news/world/africa/rss.xml')],
}
MOZ=('moçambique','mozambique','maputo','matola','cabo delgado','pemba','nampula','nacala','tete','beira','inhambane','gaza','manica','zambézia','zambezia','niassa','rovuma','quelimane')
AFRICA=('africa','áfrica','african','angola','tanzania','tanzânia','south africa','áfrica do sul','malawi','zambia','zâmbia','zimbabwe','zimbabué','kenya','quénia','nigeria','nigéria','ghana','ethiopia','etiópia','congo','rwanda','ruanda','uganda','somalia','somália','sudan','sudão','egypt','egipto','morocco','marrocos','senegal','namibia','namíbia','botswana','eswatini','lesotho','cabo verde')
CATEGORIES={
 'Concursos':('concurso público','public tender','call for proposals','invitation to bid','request for proposal','request for quotation','licitação','concurso','tender'),
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

def clean(value): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value or ''))).strip()
def norm(value):
 value=unicodedata.normalize('NFKD',value.lower()).encode('ascii','ignore').decode()
 return re.sub(r'[^a-z0-9 ]',' ',value)
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
def age(value): return (datetime.now(timezone.utc)-value).total_seconds()/3600 if value else 99999
def region(text):
 text=text.lower()
 if any(term in text for term in MOZ):return 'Moçambique'
 if any(term in text for term in AFRICA):return 'África'
 return 'Mundo'
def category(text):
 text=text.lower()
 for name,signals in CATEGORIES.items():
  if any(signal in text for signal in signals):return name
 return None
def deadline(text,language):
 for pattern in (r'(?:prazo|até|deadline|closes?|closing date)\s*[:\-]?\s*((?:\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})|(?:\d{1,2}\s+(?:de\s+)?[A-Za-zÀ-ÿ]+\s+(?:de\s+)?\d{4}))',r'((?:\d{1,2}\s+(?:de\s+)?[A-Za-zÀ-ÿ]+\s+(?:de\s+)?\d{4}))'):
  match=re.search(pattern,text,re.I)
  if match:return match.group(1).strip()
 return 'Confirmar na fonte original' if language=='pt' else 'Confirm in the original source'
def action(name,language):
 if language=='en':
  return {'Concursos':'Check the specifications, deadline and required documents before preparing a bid.','Procurement':'Check supplier requirements and register interest with the contracting entity.','Financiamento':'Confirm eligibility, available amount, deadline and application documents.','Empregos estratégicos':'Confirm the employer, location, requirements and application deadline.','Regulação & decretos':'Read the official text and assess changes to licences, costs or obligations.'}.get(name,'Confirm the responsible entity, requirements and next milestone in the original source.')
 return {'Concursos':'Confirmar o caderno de encargos, o prazo e os documentos antes de preparar a proposta.','Procurement':'Confirmar os requisitos de fornecedor e manifestar interesse junto da entidade contratante.','Financiamento':'Confirmar a elegibilidade, o montante disponível, o prazo e os documentos de candidatura.','Empregos estratégicos':'Confirmar a entidade empregadora, a localização, os requisitos e o prazo de candidatura.','Regulação & decretos':'Ler o texto oficial e avaliar alterações a licenças, custos ou obrigações.'}.get(name,'Confirmar a entidade responsável, os requisitos e o próximo marco na fonte original.')
def make_item(title,summary,source,published,link,language):
 text=f'{title} {summary}'; name=category(text)
 if not name or any(term in text.lower() for term in NEGATIVE):return None
 if not link.startswith(('http://','https://')) or 'news.google.com' in link.lower():return None
 location=region(text)
 if location=='Mundo' and source in ('Diário Económico — Concursos','Diário Económico','O País','Jornal Notícias'):location='Moçambique'
 score=(4 if location=='Moçambique' else 2 if location=='África' else 1)+(3 if name in ('Concursos','Procurement','Financiamento','Empregos estratégicos') else 2)
 fallback='Confirmar na fonte original' if language=='pt' else 'Confirm in the original source'
 return {'section':location,'category':name,'title':title,'summary':summary[:650],'entity':source,'deadline':deadline(text,language),'eligibility':fallback,'why':'O sinal contém uma acção, candidatura, contratação ou alteração concreta que merece verificação.' if language=='pt' else 'The signal contains a concrete application, contracting or regulatory action that should be verified.','action':action(name,language),'source':source,'published':published.isoformat(),'age_hours':round(max(0,age(published)),1),'link':link,'original_source':True,'verification_status':fallback,'actionability_score':score}
def parse(source,url,language):
 request=Request(url,headers={'User-Agent':'Mozilla/5.0 BriefingDiario/16','Accept':'application/rss+xml, application/xml, text/xml, */*'})
 with urlopen(request,timeout=25) as response: feed=feedparser.parse(response.read())
 output=[]
 for entry in feed.entries:
  title=clean(entry.get('title')); summary=clean(entry.get('summary') or entry.get('description')); published=published_at(entry)
  if not title or len(summary)<40 or not published or age(published)<0 or age(published)>WINDOW_HOURS:continue
  item=make_item(title,summary,source,published,entry.get('link','').strip(),language)
  if item:output.append(item)
 return output
def duplicate(candidate,selected):
 title=norm(candidate['title'])
 return any(SequenceMatcher(None,title,norm(item['title'])).ratio()>=.76 for item in selected)
def build(language):
 items=[]
 for source,url in SOURCES[language]:
  try:items.extend(parse(source,url,language))
  except Exception as error:print('feed',source,type(error).__name__,str(error)[:160])
 items.sort(key=lambda item:(item['actionability_score'],-item['age_hours']),reverse=True)
 selected=[]; counts={}
 for item in items:
  if counts.get(item['source'],0)>=MAX_PER_SOURCE or duplicate(item,selected):continue
  selected.append(item); counts[item['source']]=counts.get(item['source'],0)+1
  if len(selected)==MAX_ITEMS:break
 selected.sort(key=lambda item:item['published'],reverse=True)
 return {'updated_at':datetime.now(timezone.utc).isoformat(),'language':language,'window_days':7,'items':selected,'categories':list(CATEGORIES),'note':'Radar editorial: apenas sinais accionáveis com ligação directa. Confirme sempre os requisitos na fonte original.' if language=='pt' else 'Editorial radar: only actionable signals with direct links. Always confirm requirements in the original source.','generator':'GitHub Actions · Radar de Oportunidades'}

Path('docs/opportunities-pt.json').write_text(json.dumps(build('pt'),ensure_ascii=False,indent=2),encoding='utf-8')
Path('docs/opportunities-en.json').write_text(json.dumps(build('en'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Radar de oportunidades actualizado.')
