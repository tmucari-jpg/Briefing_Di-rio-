let data = [];
let opportunities = [];
let section = 'Mundo';
let topic = 'Todos';
let lang = localStorage.getItem('briefingLang') || 'pt';
if (!['pt', 'en'].includes(lang)) lang = 'pt';

let deferredPrompt = null;
const MAX_NEWS = 10;
const $ = selector => document.querySelector(selector);
const $$ = selector => document.querySelectorAll(selector);

const UI = {
  pt: {
    title: 'Mundo · África · Moçambique', updated: 'A carregar…', edition: 'EDIÇÃO DO DIA',
    hero: '10 notícias relevantes para acompanhar', sub: 'Últimas 24 horas · contexto, impacto e oportunidades.',
    listen: '▶ Ouvir briefing', news: 'Notícias', install: '＋ Instalar', source: 'Fonte original ↗',
    audio: '🔊 Ouvir', all: 'Todos', empty: 'Sem notícias neste filtro.', try: 'Experimente “Todos” ou outro tema.',
    curation: 'Curadoria editorial', curationText: 'Relevância, actualidade, qualidade da fonte e diversidade editorial.',
    risks: 'Riscos', risksHint: 'Abrir análise de riscos', opportunities: 'Oportunidades', opportunitiesHint: 'Abrir radar de oportunidades',
    noOpportunities: 'Nenhuma oportunidade accionável publicada nesta edição.', openOpportunity: 'Consultar oportunidade ↗'
  },
  en: {
    title: 'World · Africa · Mozambique', updated: 'Loading…', edition: 'TODAY’S EDITION',
    hero: '10 relevant stories to follow', sub: 'Last 24 hours · context, impact and opportunities.',
    listen: '▶ Listen briefing', news: 'News', install: '＋ Install', source: 'Original source ↗',
    audio: '🔊 Listen', all: 'All', empty: 'No news in this filter.', try: 'Try “All” or another filter.',
    curation: 'Editorial curation', curationText: 'Relevance, recency, source quality and editorial diversity.',
    risks: 'Risks', risksHint: 'Open risk analysis', opportunities: 'Opportunities', opportunitiesHint: 'Open opportunity radar',
    noOpportunities: 'No actionable opportunity was published in this edition.', openOpportunity: 'View opportunity ↗'
  }
};

function t(key) { return UI[lang][key]; }

function speak(text) {
  if (!('speechSynthesis' in window)) {
    alert(lang === 'pt' ? 'O áudio não é suportado neste navegador.' : 'Audio is not supported in this browser.');
    return;
  }
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang === 'pt' ? 'pt-PT' : 'en-US';
  utterance.rate = .94;
  speechSynthesis.speak(utterance);
}

function setActive(group, value) {
  $$(group + ' button').forEach(button => button.classList.toggle('active', button.dataset.section === value || button.dataset.topic === value));
}

function filteredItems() {
  return data.filter(item => item && item.section === section && (topic === 'Todos' || (Array.isArray(item.tags) && item.tags.includes(topic))));
}

function render() {
  const items = filteredItems().slice(0, MAX_NEWS);
  $('#count').textContent = `${items.length} ${lang === 'pt' ? (items.length === 1 ? 'notícia' : 'notícias') : (items.length === 1 ? 'story' : 'stories')}`;
  $('#news').innerHTML = '';
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.innerHTML = `<strong>${t('empty')}</strong><span>${t('try')}</span>`;
    $('#news').append(empty);
    return;
  }
  items.forEach(item => {
    const card = $('#card').content.cloneNode(true);
    card.querySelector('.meta').textContent = `${item.source || 'Fonte'} · ${item.published || 'Hoje'} · ${item.source_tier || ''}`;
    card.querySelector('h3').textContent = item.title || '';
    card.querySelector('.summary').textContent = item.summary || '';
    card.querySelector('.why').textContent = item.why || '';
    card.querySelector('.impact').textContent = item.impact || '';
    const link = card.querySelector('a');
    link.href = item.link || '#';
    link.textContent = t('source');
    const audio = card.querySelector('.speak');
    audio.textContent = t('audio');
    audio.onclick = () => speak(`${item.title || ''}. ${item.summary || ''}. ${item.why || ''}. ${item.impact || ''}`);
    $('#news').append(card);
  });
}

function summaryHeading(icon, title, hint) {
  const summary = document.createElement('summary');
  const symbol = document.createElement('span');
  symbol.className = 'insight-icon';
  symbol.textContent = icon;
  const copy = document.createElement('div');
  const strong = document.createElement('strong');
  strong.textContent = title;
  const small = document.createElement('small');
  small.textContent = hint;
  copy.append(strong, small);
  const chevron = document.createElement('span');
  chevron.className = 'chevron';
  chevron.textContent = '⌄';
  summary.append(symbol, copy, chevron);
  return summary;
}

function renderInsights(payload) {
  const container = $('#summary');
  container.innerHTML = '';

  const curation = document.createElement('div');
  curation.className = 'insight';
  curation.innerHTML = `<span class="insight-icon">📰</span><div><strong>${t('curation')}</strong><small>${t('curationText')}</small></div>`;
  container.append(curation);

  const risks = document.createElement('details');
  risks.className = 'insight drawer risk-drawer';
  risks.append(summaryHeading('⚠️', t('risks'), t('risksHint')));
  const riskList = document.createElement('ul');
  (payload.risks || []).forEach(item => { const li = document.createElement('li'); li.textContent = item; riskList.append(li); });
  risks.append(riskList);
  container.append(risks);

  const radar = document.createElement('details');
  radar.className = 'insight drawer opportunity-drawer';
  radar.append(summaryHeading('🚀', t('opportunities'), t('opportunitiesHint')));
  const radarBody = document.createElement('div');
  radarBody.className = 'drawer-body';
  if (!opportunities.length) {
    const empty = document.createElement('p');
    empty.textContent = t('noOpportunities');
    radarBody.append(empty);
  } else {
    opportunities.slice(0, 5).forEach(item => {
      const row = document.createElement('article');
      const category = document.createElement('span');
      category.className = 'opportunity-category';
      category.textContent = item.category || item.section || t('opportunities');
      const title = document.createElement('strong');
      title.textContent = item.title || '';
      const link = document.createElement('a');
      link.href = item.link || '#';
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = t('openOpportunity');
      row.append(category, title, link);
      radarBody.append(row);
    });
  }
  radar.append(radarBody);
  container.append(radar);
}

function applyLanguage(payload = { risks: [] }) {
  document.documentElement.lang = lang === 'pt' ? 'pt-MZ' : 'en';
  $('#title').textContent = t('title');
  $('#edition').textContent = t('edition');
  $('#heroTitle').textContent = t('hero');
  $('#heroSub').textContent = t('sub');
  $('#listenAll').textContent = t('listen');
  $('#newsTitle').textContent = t('news');
  $('#install').textContent = t('install');
  $('#language').textContent = lang === 'pt' ? 'PT' : 'EN';
  $$('#topics button').forEach(button => { if (button.dataset.topic === 'Todos') button.textContent = t('all'); });
  renderInsights(payload);
  render();
}

function showError() {
  const message = lang === 'pt' ? 'Não foi possível carregar as notícias. Toque em Actualizar para tentar novamente.' : 'Could not load news. Tap Refresh to try again.';
  $('#updated').textContent = message;
  $('#news').innerHTML = `<div class="empty"><strong>${message}</strong></div>`;
}

async function fetchJson(file, force) {
  const url = new URL(file, location.href);
  url.searchParams.set('v', force ? Date.now() : 'live');
  const response = await fetch(url.toString(), { cache: 'no-store' });
  if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
  return response.json();
}

async function load(force = false) {
  try {
    const newsFile = lang === 'pt' ? 'news-pt.json' : 'news-en.json';
    const opportunitiesFile = lang === 'pt' ? 'opportunities-pt.json' : 'opportunities-en.json';
    let payload;
    try { payload = await fetchJson(newsFile, force); }
    catch (error) { if (lang !== 'pt') throw error; payload = await fetchJson('news.json', true); }
    if (!payload || !Array.isArray(payload.items)) throw new Error('invalid data');
    const radar = await fetchJson(opportunitiesFile, force).catch(() => ({ items: [] }));
    data = payload.items;
    opportunities = Array.isArray(radar.items) ? radar.items : [];
    const updated = new Date(payload.updated_at);
    $('#updated').textContent = payload.updated_at ? `${lang === 'pt' ? 'Actualizado' : 'Updated'} ${isNaN(updated.getTime()) ? payload.updated_at : updated.toLocaleString(lang === 'pt' ? 'pt-MZ' : 'en-GB')}` : t('updated');
    applyLanguage(payload);
  } catch (error) {
    console.error('Briefing:', error);
    showError();
  }
}

function bind() {
  $$('#sections button').forEach(button => button.onclick = () => {
    section = button.dataset.section;
    topic = 'Todos';
    setActive('#sections', section);
    setActive('#topics', 'Todos');
    render();
  });
  $$('#topics button').forEach(button => button.onclick = () => {
    topic = button.dataset.topic;
    setActive('#topics', topic);
    render();
  });
  $('#listenAll').onclick = () => speak(filteredItems().slice(0, MAX_NEWS).map(item => `${item.title || ''}. ${item.summary || ''}. ${item.why || ''}. ${item.impact || ''}`).join(' '));
  $('#refresh').onclick = () => load(true);
  $('#install').onclick = () => {
    if (deferredPrompt) { deferredPrompt.prompt(); deferredPrompt = null; }
    else alert(lang === 'pt' ? 'Abra o menu ⋮ do navegador e escolha “Adicionar ao ecrã inicial” ou “Instalar aplicação”.' : 'Open the browser ⋮ menu and choose “Add to home screen” or “Install app”.');
  };
  $('#language').onclick = () => { lang = lang === 'pt' ? 'en' : 'pt'; localStorage.setItem('briefingLang', lang); load(true); };
}

bind();
load();
window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); deferredPrompt = event; });
window.addEventListener('appinstalled', () => { deferredPrompt = null; });
if ('serviceWorker' in navigator) navigator.serviceWorker.getRegistrations().then(registrations => Promise.all(registrations.map(registration => registration.unregister())));
