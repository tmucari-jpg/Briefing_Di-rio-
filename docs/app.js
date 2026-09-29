let data = [];
let opportunities = [];
let section = 'Mundo';
let topic = 'Todos';
let lang = localStorage.getItem('briefingLang') || 'pt';
if (!['pt', 'en'].includes(lang)) lang = 'pt';

let deferredPrompt = null;
const isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
let availableVoices = [];
let speechSession = 0;
let audioPlaying = false;
const MAX_NEWS = 20;
const $ = selector => document.querySelector(selector);
const $$ = selector => document.querySelectorAll(selector);

const UI = {
  pt: {
    title: 'Mundo · África · Moçambique', updated: 'A carregar…', edition: 'EDIÇÃO DO DIA',
    hero: 'Notícias essenciais para acompanhar', sub: 'Actualidade · contexto, impacto e oportunidades.',
    listen: '▶ Ouvir notícias', news: 'Notícias', install: '＋ Instalar', source: 'Consultar fonte original ↗',
    audio: '🔊 Ouvir', all: 'Todos', empty: 'Sem notícias neste filtro.', try: 'Experimente “Todos” ou outro tema.',
    opportunities: 'Oportunidades', opportunitiesHint: 'Abrir radar de oportunidades',
    noOpportunities: 'Nenhuma oportunidade accionável publicada nesta edição.', openOpportunity: 'Consultar oportunidade ↗',
    stop: '■ Parar áudio'
  },
  en: {
    title: 'World · Africa · Mozambique', updated: 'Loading…', edition: 'TODAY’S EDITION',
    hero: 'Essential stories to follow', sub: 'Latest developments · context, impact and opportunities.',
    listen: '▶ Listen to news', news: 'News', install: '＋ Install', source: 'View original source ↗',
    audio: '🔊 Listen', all: 'All', empty: 'No news in this filter.', try: 'Try “All” or another filter.',
    opportunities: 'Opportunities', opportunitiesHint: 'Open opportunity radar',
    noOpportunities: 'No actionable opportunity was published in this edition.', openOpportunity: 'View opportunity ↗',
    stop: '■ Stop audio'
  }
};

function t(key) { return UI[lang][key]; }

function normaliseSpeech(text) {
  return String(text || '')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/\bIA\b/g, lang === 'pt' ? 'inteligência artificial' : 'artificial intelligence')
    .replace(/\bLNG\b/g, lang === 'pt' ? 'gás natural liquefeito' : 'liquefied natural gas')
    .replace(/\bONU\b/g, lang === 'pt' ? 'Nações Unidas' : 'United Nations')
    .replace(/\bEUA\b/g, lang === 'pt' ? 'Estados Unidos' : 'United States')
    .replace(/(\d+(?:[.,]\d+)?)\s*%/g, `$1 ${lang === 'pt' ? 'por cento' : 'percent'}`)
    .replace(/[•·|]/g, '. ')
    .replace(/[–—]/g, ', ')
    .replace(/\s+/g, ' ')
    .trim();
}

function speechChunks(text) {
  const sentences = normaliseSpeech(text).split(/(?<=[.!?])\s+/).filter(Boolean);
  const chunks = [];
  sentences.forEach(sentence => {
    if (sentence.length <= 210) { chunks.push(sentence); return; }
    const parts = sentence.split(/(?<=[,;:])\s+/);
    let current = '';
    parts.forEach(part => {
      if (current && `${current} ${part}`.length > 210) { chunks.push(current); current = part; }
      else current = current ? `${current} ${part}` : part;
    });
    if (current) chunks.push(current);
  });
  return chunks;
}

function completeSummary(item) {
  if (item.detailed_summary) return item.detailed_summary;
  const parts = [item.summary, item.why, item.impact].map(part => String(part || '').trim()).filter(Boolean);
  return parts.filter((part, index) => parts.findIndex(other => normaliseSpeech(other).toLowerCase() === normaliseSpeech(part).toLowerCase()) === index).join(' ');
}

function selectedVoice() {
  const locale = $('#voice').value || (lang === 'pt' ? 'pt-PT' : 'en-US');
  return availableVoices.find(voice => voice.lang.toLowerCase() === locale.toLowerCase())
    || availableVoices.find(voice => voice.lang.toLowerCase().startsWith(locale.slice(0, 2).toLowerCase()))
    || null;
}

function setSpeechState(playing) {
  audioPlaying = playing;
  $('#listenAll').textContent = playing ? t('stop') : t('listen');
}

function stopSpeaking() {
  speechSession += 1;
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  setSpeechState(false);
}

function playSegments(segments) {
  if (!('speechSynthesis' in window)) {
    alert(lang === 'pt' ? 'O áudio não é suportado neste navegador.' : 'Audio is not supported in this browser.');
    return;
  }
  if (!segments.length) return;
  const session = ++speechSession;
  speechSynthesis.cancel();
  setSpeechState(true);
  const voice = selectedVoice();
  const playNext = index => {
    if (session !== speechSession) return;
    if (index >= segments.length) { setSpeechState(false); return; }
    const segment = segments[index];
    const utterance = new SpeechSynthesisUtterance(normaliseSpeech(segment.text));
    utterance.lang = $('#voice').value || (lang === 'pt' ? 'pt-PT' : 'en-US');
    utterance.rate = .82;
    utterance.pitch = 1;
    utterance.volume = 1;
    if (voice) utterance.voice = voice;
    utterance.onend = () => window.setTimeout(() => playNext(index + 1), segment.pause || 350);
    utterance.onerror = () => { if (session === speechSession) setSpeechState(false); };
    speechSynthesis.speak(utterance);
  };
  playNext(0);
}

function speak(text) {
  playSegments(speechChunks(text).map(chunk => ({ text: chunk, pause: 380 })));
}

function speakEdition() {
  const visibleByTopic = item => topic === 'Todos' || (Array.isArray(item.tags) && item.tags.includes(topic));
  const sections = lang === 'pt'
    ? [['Mundo', 'Notícias do Mundo'], ['África', 'Notícias de África'], ['Moçambique', 'Notícias de Moçambique']]
    : [['Mundo', 'World news'], ['África', 'Africa news'], ['Moçambique', 'Mozambique news']];
  const segments = [{ text: lang === 'pt' ? 'Briefing Diário.' : 'Daily Briefing.', pause: 900 }];
  sections.forEach(([sectionName, heading]) => {
    const items = data.filter(item => item.section === sectionName && visibleByTopic(item));
    if (!items.length) return;
    segments.push({ text: `${heading}.`, pause: 900 });
    items.forEach(item => {
      segments.push({ text: `${item.title || ''}.`, pause: 550 });
      speechChunks(completeSummary(item)).forEach((chunk, chunkIndex, chunks) => {
        segments.push({ text: chunk, pause: chunkIndex === chunks.length - 1 ? 800 : 380 });
      });
    });
  });
  playSegments(segments);
}

function loadVoices() {
  if (!('speechSynthesis' in window)) return;
  availableVoices = speechSynthesis.getVoices();
  const saved = localStorage.getItem('briefingVoiceLocale');
  const allowed = ['pt-PT', 'pt-BR', 'en-US', 'en-GB'];
  $('#voice').value = allowed.includes(saved) ? saved : (lang === 'pt' ? 'pt-PT' : 'en-US');
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
    card.querySelector('.summary').textContent = completeSummary(item);
    card.querySelector('.why').hidden = true;
    card.querySelector('.impact').hidden = true;
    const link = card.querySelector('a');
    link.href = item.link || '#';
    link.textContent = t('source');
    const audio = card.querySelector('.speak');
    audio.textContent = t('audio');
    audio.onclick = () => speak(`${item.title || ''}. ${completeSummary(item)}`);
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
  $('#install').textContent = isStandalone() ? (lang === 'pt' ? '✓ Aplicação' : '✓ App') : t('install');
  $('#install').disabled = isStandalone();
  $('#language').textContent = lang === 'pt' ? 'PT' : 'EN';
  loadVoices();
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
  $('#listenAll').onclick = () => {
    if (audioPlaying) { stopSpeaking(); return; }
    speakEdition();
  };
  $('#refresh').onclick = () => load(true);
  $('#install').onclick = async () => {
    if (isStandalone()) return;
    if (deferredPrompt) {
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      return;
    }
    alert(lang === 'pt' ? 'No Chrome, abra o menu ⋮ e escolha “Instalar aplicação”. Evite “Criar atalho”, pois esse abre no navegador.' : 'In Chrome, open the ⋮ menu and choose “Install app”. Avoid “Create shortcut”, which opens in the browser.');
  };
  $('#voice').onchange = () => localStorage.setItem('briefingVoiceLocale', $('#voice').value);
  $('#language').onclick = () => { stopSpeaking(); lang = lang === 'pt' ? 'en' : 'pt'; localStorage.setItem('briefingLang', lang); load(true); };
}

bind();
load();
window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); deferredPrompt = event; });
window.addEventListener('appinstalled', () => { deferredPrompt = null; applyLanguage(); });
if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = loadVoices;
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js', { scope: './' }).catch(error => console.error('PWA:', error)));
