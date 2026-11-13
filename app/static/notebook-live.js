// Lecture companion for the Studio notebook: live transcription, Catch Up (what's missing
// from the note), Define, and flashcards. Talks to the /studio/notes/{id}/... routes in app.py.
(() => {
  const $ = id => document.getElementById(id);
  const NID = window.noteId, CSRF = window.noteCsrf;
  const editor = $('editor');
  if (!NID || !editor || !$('liveToggle')) return;

  const THRESHOLD = 0.45;   // keep in sync with THRESHOLD in analysis/gaps.py
  const GRACE_SECONDS = 45; // time to write something down before it counts as missing
  let lineCount = 0, recording = false, segments = [], latestStamp = 0;
  let checking = false, checkQueued = false, pollTimer = null, typeTimer = null;
  const openNotes = new Set();
  const toSeconds = s => { const [m, sec] = s.split(':').map(Number); return m * 60 + sec; };
  const notesText = () => editor.innerText;
  const show = tab => window.showCatchTab && window.showCatchTab(tab);

  async function api(path, body) {
    const res = await fetch(`/studio/notes/${NID}/${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.error || `Request failed (${res.status})`);
    return data;
  }

  // ---- Lecture tab: transcript ----
  function addLine(l) {
    const div = document.createElement('div');
    div.className = 'live-line';
    div.innerHTML = `<span class="live-stamp">${l.stamp}</span>`;
    div.append(l.text);
    $('liveTranscript').append(div);
    $('liveTranscript').scrollTop = $('liveTranscript').scrollHeight;
    latestStamp = toSeconds(l.stamp);
  }

  function resetTranscript() {
    $('liveTranscript').innerHTML = '<p class="live-muted">No transcript yet.</p>';
    lineCount = 0; latestStamp = 0; segments = [];
    renderGaps();
  }

  async function poll() {
    const data = await api(`live/status?since=${lineCount}`);
    if (lineCount === 0 && data.lines.length) $('liveTranscript').innerHTML = '';
    data.lines.forEach(addLine);
    lineCount = data.total;
    setRecording(data.recording);
    if (data.lines.length && $('liveAuto').checked) checkGaps();
  }

  function setRecording(on) {
    recording = on;
    const btn = $('liveToggle');
    btn.textContent = on ? '■ Stop' : '● Start live transcription';
    btn.classList.toggle('stop', on);
    btn.classList.toggle('primary', !on);
    $('liveStatus').textContent = on ? 'Recording…' : (lineCount ? `${lineCount} lines saved` : 'Idle');
    $('liveImport').disabled = on;
    if (on && !pollTimer) pollTimer = setInterval(() => poll().catch(console.error), 2000);
    if (!on && pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  $('liveToggle').onclick = async () => {
    const btn = $('liveToggle');
    btn.disabled = true;
    try {
      if (recording) {
        $('liveStatus').textContent = 'Finishing last chunk…';
        await api('live/stop', {});
        await poll();
        await checkGaps();
      } else {
        if (lineCount && !confirm('Start a new recording? It replaces the transcript saved with this note.')) return;
        resetTranscript();
        $('liveStatus').textContent = 'Loading Whisper (first time takes a bit)…';
        await api('live/start', {});
        await poll();
      }
    } catch (e) {
      $('liveStatus').textContent = 'Error: ' + e.message;
    } finally {
      btn.disabled = false;
    }
  };

  // import a .txt transcript (lines like "[01:30] text", or plain text) - demo / backup if there's no mic
  $('liveImport').onclick = () => $('liveImportFile').click();
  $('liveImportFile').onchange = async () => {
    const file = $('liveImportFile').files[0];
    $('liveImportFile').value = '';
    if (!file) return;
    try {
      await api('live/import', { text: await file.text() });
      resetTranscript();
      await poll();
      $('liveStatus').textContent = `Imported ${file.name}`;
      await checkGaps();
      show('catch');
    } catch (e) {
      $('liveStatus').textContent = 'Error: ' + e.message;
    }
  };

  // ---- Catch Up tab: what's missing from the note ----
  async function checkGaps() {
    if (!lineCount) return;
    if (checking) { checkQueued = true; return; }
    checking = true;
    $('liveCheck').disabled = true;
    try {
      segments = (await api('live/gaps', { notes: notesText() })).segments;
      renderGaps();
    } catch (e) {
      console.error('Catch Up failed', e);
    } finally {
      checking = false;
      $('liveCheck').disabled = false;
      if (checkQueued) { checkQueued = false; checkGaps(); }
    }
  }

  // keep in sync with is_flagged() in analysis/gaps.py
  const isGap = w => w.important && (w.score < THRESHOLD || w.names.length > 0);
  const isRecent = w => recording && latestStamp - toSeconds(w.stamp) < GRACE_SECONDS;

  function addToNote(w, btn) {
    const p = document.createElement('p');
    p.textContent = w.text;
    editor.appendChild(p);
    editor.dispatchEvent(new Event('input', { bubbles: true }));  // triggers autosave + re-check
    btn.textContent = 'Added ✓';
    btn.disabled = true;
  }

  function gapItem(w, recent) {
    const div = document.createElement('div');
    div.className = recent ? 'live-gap recent' : 'live-gap';
    div.innerHTML = `<span class="live-stamp">${w.stamp}</span>`;
    if (w.names.length) {
      const t = document.createElement('div');
      t.className = 'live-muted';
      t.textContent = 'Not in notes: ' + w.names.join(', ');
      div.append(t);
    }
    div.append(w.text);
    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'live-btn';
    add.textContent = '+ Add to note';
    add.onclick = () => addToNote(w, add);
    div.append(document.createElement('br'), add);
    return div;
  }

  function label(parent, text) {
    const d = document.createElement('div');
    d.className = 'live-group';
    d.textContent = text;
    parent.append(d);
  }

  function renderGaps() {
    const box = $('liveGaps');
    box.innerHTML = '';
    let missingTotal = 0;
    if (!segments.length) {
      box.innerHTML = `<p class="live-muted">${lineCount ? 'Checking…' : "Record or import a lecture to see what's missing from your notes."}</p>`;
      $('gapCount').textContent = '';
      return;
    }
    for (const seg of segments) {
      const settled = seg.windows.filter(w => !isRecent(w) && w.important);
      const missing = settled.filter(isGap);
      const recent = seg.windows.filter(w => isRecent(w) && isGap(w));
      const covered = settled.length - missing.length;
      const pct = settled.length ? Math.round(100 * covered / settled.length) : 100;
      missingTotal += missing.length;

      const card = document.createElement('div');
      card.className = 'live-segment';
      const head = document.createElement('div');
      head.className = 'live-seg-head';
      const title = document.createElement('span');
      title.textContent = seg.title;
      const time = document.createElement('span');
      time.className = 'live-stamp';
      time.textContent = `${seg.start}–${seg.end}`;
      head.append(title, time);
      const bar = document.createElement('div');
      bar.className = 'live-bar' + (pct < 50 ? ' low' : pct < 80 ? ' mid' : '');
      bar.innerHTML = `<div style="width:${pct}%"></div>`;
      const stat = document.createElement('div');
      stat.className = 'live-muted';
      stat.textContent = settled.length ? `${pct}% covered (${covered}/${settled.length})` : 'In progress';
      card.append(head, bar, stat);

      if (missing.length) { label(card, 'Missing'); missing.forEach(w => card.append(gapItem(w, false))); }
      if (recent.length) { label(card, 'Just said'); recent.forEach(w => card.append(gapItem(w, true))); }
      if (seg.notes.length) {
        const det = document.createElement('details');
        det.innerHTML = `<summary class="live-muted">Your notes here (${seg.notes.length})</summary>`;
        det.open = openNotes.has(seg.id);
        det.ontoggle = () => det.open ? openNotes.add(seg.id) : openNotes.delete(seg.id);
        const ul = document.createElement('ul');
        seg.notes.forEach(n => { const li = document.createElement('li'); li.className = 'live-muted'; li.textContent = n; ul.append(li); });
        det.append(ul);
        card.append(det);
      }
      box.append(card);
    }
    $('gapCount').textContent = missingTotal ? String(missingTotal) : '';
  }

  $('liveCheck').onclick = checkGaps;
  editor.addEventListener('input', () => {
    clearTimeout(typeTimer);
    typeTimer = setTimeout(() => { if ($('liveAuto').checked) checkGaps(); }, 2000);
  });

  // ---- Flashcards ----
  $('makeCards').onclick = async () => {
    const btn = $('makeCards'), out = $('cardsResult');
    btn.disabled = true;
    out.textContent = $('cardsAi').checked ? 'Writing questions… (the first run loads the model)' : 'Making cards…';
    try {
      const d = await api('cards', { notes: notesText(), use_ai: $('cardsAi').checked });
      out.innerHTML = d.added
        ? `Added ${d.added} flashcard(s). ${d.info || ''} <a href="/studio/study">Practice them →</a>`
        : 'Those flashcards are already in this class.';
    } catch (e) {
      out.textContent = e.message;
    } finally {
      btn.disabled = false;
    }
  };

  // ---- Define tab ----
  let term = '', definition = '', busy = false;
  const labels = { define: 'Definition', explain: 'More detail', example: 'Example' };

  function selectedTerm() {
    const sel = window.getSelection();
    if (!sel.rangeCount || !editor.contains(sel.anchorNode)) return '';
    const text = sel.toString().replace(/\s+/g, ' ').trim();
    return text.length && text.length <= 100 && text.split(' ').length <= 8 ? text : '';
  }

  async function ask(mode) {
    if (busy) return;
    busy = true;
    $('defineFollowup').querySelectorAll('button').forEach(b => b.disabled = true);
    const block = document.createElement('div');
    block.className = 'define-result';
    const h = document.createElement('strong'); h.textContent = labels[mode];
    const p = document.createElement('p'); p.textContent = 'Thinking… (the first one can take a minute while the model loads)';
    const src = document.createElement('small'); src.className = 'live-muted';
    block.append(h, p, src);
    $('defineResults').append(block);
    try {
      const d = await api('define', { term, mode, previous: definition });
      p.textContent = d.text;
      src.textContent = !d.ai ? 'Not AI-generated: lines from your lecture'
        : d.grounded ? `Based on how your lecture uses "${d.term}"` : 'Not in your lecture, so this is general knowledge';
      if (mode === 'define') { definition = d.text; $('defineFollowup').hidden = false; }
      else $('defineFollowup').querySelector(`[data-mode="${mode}"]`).dataset.used = '1';
    } catch (e) {
      p.textContent = e.message;
    }
    busy = false;
    $('defineFollowup').querySelectorAll('button').forEach(b => b.disabled = !!b.dataset.used);
  }

  // mousedown preventDefault keeps the highlight in the note when the button is clicked
  $('defineSel').addEventListener('mousedown', e => e.preventDefault());
  $('defineSel').onclick = () => {
    const t = selectedTerm();
    show('define');
    if (!t) {
      $('defineEmpty').hidden = false;
      $('defineEmpty').innerHTML = 'Highlight a word or short phrase (up to 8 words) in your note, then click <b>Define</b>.';
      return;
    }
    term = t; definition = '';
    $('defineEmpty').hidden = true;
    $('defineBox').hidden = false;
    $('defineTerm').textContent = term;
    $('defineResults').innerHTML = '';
    $('defineFollowup').hidden = true;
    $('defineFollowup').querySelectorAll('button').forEach(b => delete b.dataset.used);
    ask('define');
  };
  $('defineFollowup').querySelectorAll('button').forEach(b => b.onclick = () => ask(b.dataset.mode));

  // load the transcript saved with this note (or pick up a recording in progress after a refresh)
  poll().then(() => { if (lineCount) checkGaps(); }).catch(() => {});
})();