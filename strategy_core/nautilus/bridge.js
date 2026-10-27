/* Nautilus 1.1 display controller. Layout preferences only; no engine writes. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const body = document.body;
  const chart = window.__nautilus.chart;
  const key = 'nautilus.display.v1.1';
  const modes = ['auto', 'bridge', 'desktop', 'tablet', 'mobile'];
  const names = {auto:'Auto', bridge:'TV / Bridge', desktop:'Desktop', tablet:'Tablet', mobile:'Phone'};
  let preference = {mode:'auto', scale:null}, previousLayout = null, noticeTimer, resizeFrame;
  try {
    const saved = JSON.parse(localStorage.getItem(key));
    if (saved && modes.includes(saved.mode)) preference.mode = saved.mode;
    if (saved && [1, 1.15, 1.3].includes(saved.scale)) preference.scale = saved.scale;
  } catch (_) { /* Private mode and unavailable storage keep safe defaults. */ }
  const save = () => { try { localStorage.setItem(key, JSON.stringify(preference)); } catch (_) {} };
  function notice(text) {
    clearTimeout(noticeTimer);
    $('displayNotice').textContent = text;
    $('displayNotice').classList.remove('hidden');
    noticeTimer = setTimeout(() => $('displayNotice').classList.add('hidden'), 9000);
  }
  function resolvedMode() {
    const width = window.innerWidth, selected = preference.mode;
    if (selected === 'mobile') return 'mobile';
    if (width < 700) return 'mobile';
    if (selected === 'tablet' || width < 1150) return 'tablet';
    if (selected === 'bridge' || selected === 'desktop') return selected;
    return width >= 1400 ? 'bridge' : 'desktop';
  }
  function setRight(section) {
    if (!['positions','briefing','navigator'].includes(section)) return;
    body.dataset.right = section;
    const visible = {positions:['positionsPanel','tradesPanel','protectionPanel'],briefing:['briefingPanel'],navigator:['navigatorPanel']}[section];
    for (const id of ['positionsPanel','tradesPanel','protectionPanel','briefingPanel','navigatorPanel']) {
      $(id).classList.toggle('display-hidden', !visible.includes(id));
    }
    document.querySelectorAll('[data-right]').forEach(button => {
      if (button.tagName === 'BUTTON') {
        button.classList.toggle('active', button.dataset.right === section);
        button.setAttribute('aria-pressed', String(button.dataset.right === section));
      }
    });
  }
  function setDeck(section) {
    if (!['chart','positions','feed','trades','decisions','briefing'].includes(section)) return;
    body.dataset.deck = section;
    document.querySelectorAll('button[data-deck]').forEach(button => {
      button.classList.toggle('active', button.dataset.deck === section);
      button.setAttribute('aria-pressed', String(button.dataset.deck === section));
    });
    if (section === 'positions' || section === 'briefing') setRight(section);
    if (section === 'trades' || section === 'decisions') {
      setRight('positions');
      document.querySelector(`button[data-tab="${section}"]`).click();
    }
    chart.requestDraw();
  }
  function apply() {
    const mode = resolvedMode();
    const scale = preference.scale ?? (mode === 'bridge' ? 1.15 : 1);
    const screenFactor = mode === 'bridge' ? Math.min(1.35, Math.max(1, innerWidth / 2200)) : 1;
    body.dataset.layout = mode;
    body.dataset.lowHeight = String(innerHeight < 560 || (mode === 'mobile' && innerHeight < 680));
    body.style.setProperty('--type-scale', String(scale * screenFactor));
    chart.fontScale = Math.min(1.4, scale * screenFactor);
    $('layoutMode').value = preference.mode;
    $('readability').value = String(scale);
    $('displaySettings').textContent = mode === 'mobile' ? 'Display' : 'Display: ' + names[preference.mode];
    $('bridgeFullscreen').textContent = document.fullscreenElement === document.documentElement ? '↙ Exit fullscreen' : mode === 'mobile' ? '⛶ Fullscreen' : '⛶ Fullscreen';
    chart.compactLabels = mode === 'mobile';
    $('displaySettings').title = names[mode] + ' layout · ' + Math.round(scale * 100) + '% text';
    $('displayResolution').textContent = `${innerWidth} × ${innerHeight} CSS pixels · ${names[mode]} layout · ${Math.round(scale * 100)}% text. Screen size is measured by available browser space, not TV inches.`;
    if (preference.mode !== 'auto' && preference.mode !== mode) {
      $('displayResolution').textContent += ' The selected layout falls back on narrow screens so panels remain accessible.';
    }
    if (previousLayout !== mode) {
      setDeck(mode === 'tablet' ? 'feed' : 'chart');
      previousLayout = mode;
    }
    // Typography and viewport geometry change; chart time, zoom and follow state do not.
    chart.requestDraw();
  }
  $('displaySettings').onclick = () => { apply(); $('displayDialog').showModal(); };
  $('closeDisplay').onclick = () => $('displayDialog').close();
  $('displayDialog').onclick = event => { if (event.target === $('displayDialog')) $('displayDialog').close(); };
  $('layoutMode').onchange = event => { preference.mode = event.target.value; save(); apply(); };
  $('readability').onchange = event => { preference.scale = Number(event.target.value); save(); apply(); };
  $('resetDisplay').onclick = () => { preference = {mode:'auto',scale:null}; save(); apply(); };
  document.querySelectorAll('button[data-right]').forEach(button => button.onclick = () => setRight(button.dataset.right));
  document.querySelectorAll('button[data-deck]').forEach(button => button.onclick = () => setDeck(button.dataset.deck));
  $('zoomIn').onclick = () => chart.setSpan(chart.span / 1.25);
  $('zoomOut').onclick = () => chart.setSpan(chart.span * 1.25);

  async function fullscreen(target) {
    try {
      if (document.fullscreenElement === target) {
        await document.exitFullscreen();
      } else if (typeof target.requestFullscreen === 'function') {
        await target.requestFullscreen();
      } else {
        notice('Fullscreen is not available in this browser. Use browser fullscreen (F11 on Windows); the layout will still fit the viewport.');
      }
    } catch (_) {
      notice('The browser did not allow fullscreen. Use F11 on Windows, or remain in the fitted window layout.');
    }
  }
  $('bridgeFullscreen').onclick = () => fullscreen(document.documentElement);
  $('fullChart').onclick = () => fullscreen($('chartPanel'));
  function fullscreenState() {
    const whole = document.fullscreenElement === document.documentElement;
    const chartOnly = document.fullscreenElement === $('chartPanel');
    $('bridgeFullscreen').textContent = whole ? '↙ Exit fullscreen' : '⛶ Fullscreen';
    $('bridgeFullscreen').setAttribute('aria-pressed', String(whole));
    $('fullChart').textContent = chartOnly ? '↙' : '⛶';
    $('fullChart').title = chartOnly ? 'Exit chart fullscreen' : 'Chart fullscreen';
    $('fullChart').setAttribute('aria-label', $('fullChart').title);
    $('fullChart').setAttribute('aria-pressed', String(chartOnly));
    apply();
  }
  document.addEventListener('fullscreenchange', fullscreenState);
  window.addEventListener('resize', () => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(apply);
  });
  window.visualViewport?.addEventListener('resize', () => chart.requestDraw());
  document.addEventListener('nautilus:trade-selected', () => {
    $('briefingTab').textContent = 'Trade review';
    setRight('briefing');
    if (['tablet','mobile'].includes(body.dataset.layout)) setDeck('briefing');
  });
  document.addEventListener('nautilus:monitor', () => {
    $('briefingTab').textContent = 'Briefing';
    setRight('positions');
    if (body.dataset.layout === 'mobile') setDeck('chart');
  });
  // Keyboard-focusable tab groups remain normal buttons; no focus trapping here.
  setRight('positions');
  apply();
  window.__nautilus.display = {apply, setDeck, setRight, resolvedMode, getPreference:() => ({...preference})};
})();
