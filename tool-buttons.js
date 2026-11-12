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
    });
  });
  document.getElementById('closeToolSelection').addEventListener('click', () => {
    details.hidden = true;
    cards.forEach(c => c.setAttribute('aria-pressed', 'false'));
  });
});
