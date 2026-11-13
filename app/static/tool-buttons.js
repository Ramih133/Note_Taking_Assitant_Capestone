// Each tool has a stable data-tool identifier for connecting an API later.
document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.ai-tool-card');
  const details = document.getElementById('aiToolSelection');
  const title = document.getElementById('selectedToolTitle');
  const description = document.getElementById('selectedToolDescription');
  cards.forEach(card => {
    card.setAttribute('aria-pressed', 'false');
    card.addEventListener('click', () => {
      cards.forEach(c => c.setAttribute('aria-pressed', 'false'));
      card.setAttribute('aria-pressed', 'true');
      title.textContent = card.dataset.title;
      description.textContent = card.dataset.description;
      details.hidden = false;
      // wire the run form to this tool
      document.getElementById('toolKind').value = card.dataset.tool;
      document.getElementById('toolExtraLabel').textContent = {
        ask: 'Your question',
        catchup: 'Paste the lecture transcript (required)',
        planner: 'Your goals and exam dates',
        coding: 'Paste the code',
        math: 'Paste the problem',
      }[card.dataset.tool] || 'Extra text (optional, used with or instead of the note)';
      document.getElementById('toolOutput').textContent = '';
      document.getElementById('toolMode').textContent = '';
      document.getElementById('copyTool').hidden = true;
    });
  });
  document.getElementById('closeToolSelection').addEventListener('click', () => {
    details.hidden = true;
    cards.forEach(c => c.setAttribute('aria-pressed', 'false'));
  });
});