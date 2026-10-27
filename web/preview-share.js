(() => {
  const link = document.querySelector('#sharePreview');
  if (!link || !location.hostname.endsWith('.vercel.run')) return;
  link.hidden = false;
  link.title = 'Share the public Montara link. Each person opens their own private preview.';
  link.addEventListener('click', async event => {
    if (!navigator.clipboard) return;
    event.preventDefault();
    try {
      await navigator.clipboard.writeText(link.href);
      link.textContent = 'Link copied';
      setTimeout(() => { link.textContent = 'Share Montara'; }, 2500);
    } catch {
      link.textContent = 'montara-tau.vercel.app';
    }
  });
})();
