// Files tab for the Studio notebook: upload slides / recordings / lecture text / notes files for
// this note, and run Analyze my notes. Talks to /studio/notes/{id}/files and /analyze in app.py.
(() => {
  const $ = id => document.getElementById(id);
  const NID = window.noteId, CSRF = window.noteCsrf;
  const editor = $('editor');
  if (!NID || !editor || !$('filesTab')) return;

  const KIND = { slides: 'Slides', recording: 'Recording', lecture: 'Lecture text', notes: 'Notes file' };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let pollTimer = null;

  async function call(path, opts = {}) {
    const res = await fetch(`/studio/notes/${NID}/${path}`, {
      credentials: 'same-origin', ...opts, headers: { 'X-CSRF-Token': CSRF, ...(opts.headers || {}) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { const e = new Error(data.error || data.detail || `Request failed (${res.status})`); e.data = data; throw e; }
    return data;
  }

  function render(data) {
    const files = data.files || [];
    $('fileList').innerHTML = files.length
      ? files.map(f => `<div class="file-row"><span>${KIND[f.kind] || f.kind}: ${esc(f.original_name)}</span>
          <button type="button" class="live-btn" data-del="${f.id}" title="Remove">✕</button></div>`).join('')
      : '<p class="live-muted">No files yet.</p>';
    if (data.job) $('fileStatus').textContent = data.job;
    clearTimeout(pollTimer);
    if ((data.job || '').startsWith('Transcribing')) pollTimer = setTimeout(refresh, 5000);
  }

  const refresh = () => call('files').then(render).catch(() => {});

  $('fileUpload').onclick = async () => {
    const file = $('fileInput').files[0];
    if (!file) { $('fileStatus').textContent = 'Choose a file first.'; return; }
    const fd = new FormData();
    fd.append('kind', $('fileKind').value);
    fd.append('file', file);
    $('fileUpload').disabled = true;
    $('fileStatus').textContent = `Uploading ${file.name}…`;
    try {
      const data = await call('files', { method: 'POST', body: fd });
      $('fileStatus').textContent = `Uploaded ${file.name}.`;
      if (data.notes_text) { $('fileStatus').textContent += ' Organizing it by topic…'; organize(data.notes_text); }
      if (data.transcript_filled) $('fileStatus').textContent += ' Using it as this note\'s transcript. Reload to see it in the Lecture tab.';
      render(data);
      $('fileInput').value = '';
    } catch (e) {
      $('fileStatus').textContent = e.message;
      if (e.data && e.data.files) render(e.data);
    } finally {
      $('fileUpload').disabled = false;
    }
  };

  $('fileList').onclick = async e => {
    const id = e.target.dataset.del;
    if (!id) return;
    try { render(await call(`files/${id}/delete`, { method: 'POST' })); }
    catch (err) { $('fileStatus').textContent = err.message; }
  };

  // sorts notes into topic sections as a new note (the uploaded file's text, or this note's)
  async function organize(text) {
    const out = $('organizeResult');
    $('organizeNotes').disabled = true;
    out.textContent = 'Organizing… (the first run loads the models)';
    try {
      const r = await call('organize', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: text }),
      });
      out.innerHTML = `Done: ${r.sections} sections${r.new_topics ? ` (${r.new_topics} new from your notes)` : ''}. <a href="${r.url}">Open the organized note</a>`;
    } catch (e) {
      out.textContent = e.message;
    } finally {
      $('organizeNotes').disabled = false;
    }
  }
  $('organizeNotes').onclick = () => organize(editor.innerText);

  $('analyzeNotes').onclick = async () => {
    const box = $('analyzeResult');
    $('analyzeNotes').disabled = true;
    box.innerHTML = '<p class="live-muted">Analyzing… (the first run loads the models)</p>';
    try {
      const r = await call('analyze', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: editor.innerText }),
      });
      const q = r.quality || {};
      box.innerHTML =
        `<h3>Notes score: ${esc(q.score)}/100</h3>` +
        (q.coverage ? `<p class="live-muted">${esc(q.coverage)} covered, weighted by importance · slides + ${esc(r.source)}</p>` : `<p>${esc(q.summary)}</p>`) +
        (q.tips || []).map(t => `<p class="live-muted">${esc(t)}</p>`).join('') +
        '<h3>High-importance points you missed</h3>' +
        ((r.missing || []).map(m => `<div class="file-row"><span><strong>${esc(m.text)}</strong><br>
          <small>Slide ${esc(m.slide)} · ${esc(m.section || m.title)}</small></span></div>`).join('')
          || '<p class="live-muted">Your notes cover all the high-importance points.</p>') +
        '<h3>Section recaps</h3>' +
        ((r.recaps || []).map(x => `<p><strong>${esc(x.section)}</strong> <small>slides ${esc(x.slides)} · ${esc(x.coverage)} covered</small></p>` +
          (x.summary ? `<p>${esc(x.summary)}</p>` : '') +
          `<ul>${(x.missing || []).map(p => `<li>${esc(p.text)} (slide ${esc(p.slide)})</li>`).join('')}</ul>`).join('')
          || '<p class="live-muted">No sections need a recap.</p>');
    } catch (e) {
      box.innerHTML = `<p class="live-muted">${esc(e.message)}</p>`;
    } finally {
      $('analyzeNotes').disabled = false;
    }
  };

  refresh();
})();
