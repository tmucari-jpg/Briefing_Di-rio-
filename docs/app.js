let data = [];
let opportunities = [];
let section = 'Mundo';
let topic = 'Todos';
let lang = localStorage.getItem('briefingLang') || 'pt';
if (!['pt', 'en'].includes(lang)) lang = 'pt';

let deferredPrompt = null;
const MAX_NEWS = 20;
const $ = selector => document.querySelector(selector);
const $$ = selector => document.querySelectorAll(selector);

const UI = {
  pt: {
    title: 'Mundo · África · Moçambique', updated: 'A carregar…', edition: 'EDIÇÃO DO DIA',
    hero: 'Notícias essenciais para acompanhar', sub: 'Actualidade · contexto, impacto e oportunidades.',
    listen: '▶ Ouvir resumos', news: 'Notícias', install: '＋ Instalar', source: 'Ler notícia completa ↗',
    audio: '🔊 Ouvir', all: 'Todos', empty: 'Sem notícias neste filtro.', try: 'Experimente “Todos” ou outro tema.',
    opportunities: 'Oportunidades', opportunitiesHint: 'Abrir radar de oportunidades',
    noOpportunities: 'Nenhuma oportunidade accionável publicada nesta edição.', openOpportunity: 'Consultar oportunidade ↗'
  },
  en: {
    title: 'World · Africa · Mozambique', updated: 'Loading…', edition: 'TODAY’S EDITION',
    hero: 'Essential stories to follow', sub: 'Latest developments · context, impact and opportunities.',
    listen: '▶ Listen to summaries', news: 'News', install: '＋ Install', source: 'Read full story ↗',
    audio: '🔊 Listen', all: 'All', empty: 'No news in this filter.', try: 'Try “All” or another filter.',
    opportunities: 'Opportunities', opportunitiesHint: 'Open opportunity radar',
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
    audio.onclick = () => speak(`${item.title || ''}. ${item.summary || ''}`);
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

  const radar = document.createElement('details');
  radar.className = 'insight drawer opportunity-drawer';
  radar.style.gridColumn = '1 / -1';
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
      const deadline = document.createElement('small');
      deadline.textContent = `${lang === 'pt' ? 'Prazo' : 'Deadline'}: ${item.deadline || (lang === 'pt' ? 'Confirmar na fonte' : 'Confirm in source')}`;
      const link = document.createElement('a');
      link.href = item.link || '#';
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = t('openOpportunity');
      row.append(category, title, deadline, link);
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
  $('#listenAll').onclick = () => speak(filteredItems().slice(0, MAX_NEWS).map(item => `${item.title || ''}. ${item.summary || ''}`).join(' '));
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
