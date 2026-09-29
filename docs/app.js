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
const translationCache = new Map();
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
    stop: '■ Parar áudio', translate: '🌐 Traduzir para inglês', original: '↩ Ver original',
    translating: 'A traduzir…', translationError: 'Não foi possível traduzir agora.'
  },
  en: {
    title: 'World · Africa · Mozambique', updated: 'Loading…', edition: 'TODAY’S EDITION',
    hero: 'Essential stories to follow', sub: 'Latest developments · context, impact and opportunities.',
    listen: '▶ Listen to news', news: 'News', install: '＋ Install', source: 'View original source ↗',
    audio: '🔊 Listen', all: 'All', empty: 'No news in this filter.', try: 'Try “All” or another filter.',
    opportunities: 'Opportunities', opportunitiesHint: 'Open opportunity radar',
    noOpportunities: 'No actionable opportunity was published in this edition.', openOpportunity: 'View opportunity ↗',
    stop: '■ Stop audio', translate: '🌐 Translate to Portuguese', original: '↩ View original',
    translating: 'Translating…', translationError: 'Translation is temporarily unavailable.'
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

function translationChunks(text, limit = 420) {
  const sentences = String(text || '').match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [];
  const chunks = [];
  let current = '';
  sentences.forEach(sentence => {
    const clean = sentence.trim();
    if (!clean) return;
    if (current && `${current} ${clean}`.length > limit) { chunks.push(current); current = ''; }
    if (clean.length <= limit) current = current ? `${current} ${clean}` : clean;
    else {
      if (current) { chunks.push(current); current = ''; }
      for (let index = 0; index < clean.length; index += limit) chunks.push(clean.slice(index, index + limit));
    }
  });
  if (current) chunks.push(current);
  return chunks;
}

async function translateText(text, source, target) {
  const clean = String(text || '').trim();
  if (!clean) return '';
  const key = `${source}:${target}:${clean}`;
  if (translationCache.has(key)) return translationCache.get(key);
  const translated = [];
  for (const chunk of translationChunks(clean)) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    try {
      const url = new URL('https://api.mymemory.translated.net/get');
      url.searchParams.set('q', chunk);
      url.searchParams.set('langpair', `${source}|${target}`);
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`Translation HTTP ${response.status}`);
      const result = await response.json();
      const translatedText = result && result.responseData && result.responseData.translatedText;
      if (!translatedText) throw new Error('Empty translation');
      const textarea = document.createElement('textarea');
      textarea.innerHTML = translatedText;
      translated.push(textarea.value);
    } finally { window.clearTimeout(timeout); }
  }
  const result = translated.join(' ');
  translationCache.set(key, result);
  return result;
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
    const originalTitle = item.title || '';
    const originalSummary = completeSummary(item);
    const heading = card.querySelector('h3');
    const summary = card.querySelector('.summary');
    card.querySelector('.meta').textContent = `${item.source || 'Fonte'} · ${item.published || 'Hoje'} · ${item.source_tier || ''}`;
    heading.textContent = originalTitle;
    summary.textContent = originalSummary;
    card.querySelector('.why').hidden = true;
    card.querySelector('.impact').hidden = true;
    const link = card.querySelector('a');
    link.href = item.link || '#';
    link.textContent = t('source');
    const audio = card.querySelector('.speak');
    audio.textContent = t('audio');
    audio.onclick = () => speak(`${heading.textContent || ''}. ${summary.textContent || ''}`);
    const actions = card.querySelector('.actions');
    actions.style.gap = '8px';
    actions.style.flexWrap = 'wrap';
    const translate = document.createElement('button');
    translate.className = 'translate';
    translate.textContent = t('translate');
    let showingTranslation = false;
    translate.onclick = async () => {
      if (showingTranslation) {
        heading.textContent = originalTitle;
        summary.textContent = originalSummary;
        translate.textContent = t('translate');
        showingTranslation = false;
        return;
      }
      translate.disabled = true;
      translate.textContent = t('translating');
      try {
        const target = lang === 'pt' ? 'en' : 'pt';
        const [translatedTitle, translatedSummary] = await Promise.all([
          translateText(originalTitle, lang, target), translateText(originalSummary, lang, target)
        ]);
        heading.textContent = translatedTitle;
        summary.textContent = translatedSummary;
        translate.textContent = t('original');
        showingTranslation = true;
      } catch (error) {
        console.error('Translation:', error);
        translate.textContent = t('translationError');
        window.setTimeout(() => { translate.textContent = t('translate'); }, 2800);
      } finally { translate.disabled = false; }
    };
    actions.insertBefore(translate, link);
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
  const radarHint = opportunities.length ? `${t('opportunitiesHint')} · ${opportunities.length}` : t('opportunitiesHint');
  radar.append(summaryHeading('🚀', t('opportunities'), radarHint));
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
      row.append(category, title, deadline);
      if (item._language && item._language !== lang) {
        const translate = document.createElement('button');
        translate.className = 'opportunity-translate';
        translate.textContent = lang === 'en' ? '🌐 Translate to English' : '🌐 Traduzir para português';
        const originalTitle = title.textContent;
        translate.onclick = async () => {
          translate.disabled = true;
          try {
            title.textContent = await translateText(originalTitle, item._language, lang === 'en' ? 'en' : 'pt');
            translate.remove();
          } catch (error) {
            translate.textContent = t('translationError');
            translate.disabled = false;
          }
        };
        row.append(translate);
      }
      row.append(link);
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
  $('#language').textContent = lang === 'pt' ? 'Fontes PT' : 'Sources EN';
  $('#language').title = lang === 'pt' ? 'Mudar para fontes em inglês' : 'Switch to Portuguese sources';
  $('#language').setAttribute('aria-label', $('#language').title);
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
  const response = await fetch(url.toString(), { cache: force ? 'no-store' : 'default' });
  if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
  return response.json();
}

async function load(force = false) {
  try {
    const newsFile = lang === 'pt' ? 'news-pt.json' : 'news-en.json';
    const newsPromise = fetchJson(newsFile, force).catch(error => {
      if (lang !== 'pt') throw error;
      return fetchJson('news.json', force);
    });
    const radarPromises = lang === 'pt'
      ? [fetchJson('opportunities-pt.json', force).catch(() => ({ items: [] }))]
      : [
          fetchJson('opportunities-en.json', force).catch(() => ({ items: [] })),
          fetchJson('opportunities-pt.json', force).catch(() => ({ items: [] }))
        ];
    const [payload, radarResults] = await Promise.all([newsPromise, Promise.all(radarPromises)]);
    if (!payload || !Array.isArray(payload.items)) throw new Error('invalid data');
    data = payload.items;
    const seenOpportunities = new Set();
    opportunities = radarResults.flatMap((radar, index) => {
      const sourceLanguage = lang === 'pt' ? 'pt' : (index === 0 ? 'en' : 'pt');
      return (Array.isArray(radar.items) ? radar.items : []).map(item => ({ ...item, _language: sourceLanguage }));
    }).filter(item => {
      const key = item.link || `${item.title || ''}:${item.deadline || ''}`;
      if (seenOpportunities.has(key)) return false;
      seenOpportunities.add(key);
      return true;
    });
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
  $('#language').onclick = () => { stopSpeaking(); lang = lang === 'pt' ? 'en' : 'pt'; localStorage.setItem('briefingLang', lang); load(false); };
}

bind();
load();
window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); deferredPrompt = event; });
window.addEventListener('appinstalled', () => { deferredPrompt = null; applyLanguage(); });
if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = loadVoices;
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js', { scope: './' }).catch(error => console.error('PWA:', error)));
