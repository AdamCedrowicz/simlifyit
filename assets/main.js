(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // The live sheet: toggle between the raw export and its one-line answer
  const sheet = document.getElementById('sheet');
  if (sheet) {
    const btn = sheet.querySelector('.sheet-toggle');
    const raw = sheet.querySelector('.sheet-raw');
    const simple = sheet.querySelector('.sheet-simple');
    sheet.querySelectorAll('.sheet-bars li').forEach((li, n) => li.style.setProperty('--n', n));
    btn.addEventListener('click', () => {
      const simplified = sheet.dataset.state === 'raw';
      sheet.dataset.state = simplified ? 'simple' : 'raw';
      raw.hidden = simplified;
      simple.hidden = !simplified;
      btn.setAttribute('aria-pressed', String(simplified));
      btn.textContent = simplified ? 'Pokaż surowe dane' : 'Uprość ten arkusz';
    });
  }

  // Section entrances: heading, then text, then figure
  const groups = [
    ['.intro', '.intro-top > *, .facts li'],
    ['.showcase', '.showcase-h, .panel'],
    ['.process', '.process h2'],
    ['.services', '.services h2'],
    ['.about', '.about-h, .about-facts > div, .about-text, .about-word, .record li'],
    ['.faq', '.faq-head h2, .qa h3, .qa p'],
    ['.contact', '.contact-line, .contact-pic, .contact-links > *'],
  ];
  const targets = [];
  groups.forEach(([section, parts]) => {
    document.querySelectorAll(section).forEach(root => {
      root.querySelectorAll(parts).forEach((el, n) => {
        el.setAttribute('data-reveal', '');
        el.style.setProperty('--n', Math.min(n, 8));
        targets.push(el);
      });
    });
  });
  const stages = document.querySelector('.stages');
  if (stages) {
    stages.querySelectorAll('.stage').forEach((s, n) => s.style.setProperty('--n', n));
    targets.push(stages);
  }
  if ('IntersectionObserver' in window && !reduce) {
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -12% 0px' });
    targets.forEach(t => io.observe(t));
  } else {
    targets.forEach(t => t.classList.add('is-in'));
  }

  // Services deck: cards fold into spines as the pinned stage scrolls
  const services = document.querySelector('.services');
  const cards = services ? [...services.querySelectorAll('.card')] : [];
  const wide = window.matchMedia('(min-width: 1000px)');
  const SPINE = 120, GAP = 12;
  let active = -1;

  function layout(index, force) {
    if (index === active && !force) return;
    active = index;
    const deckWidth = cards[0].parentElement.clientWidth;
    const last = cards.length - 1;
    cards.forEach((card, i) => {
      const x = i <= index
        ? i * (SPINE + GAP)
        : deckWidth - SPINE - (last - i) * (SPINE + GAP);
      const spine = i !== index;
      card.classList.toggle('is-spine', spine);
      if (spine) { card.setAttribute('tabindex', '0'); card.setAttribute('aria-label', card.querySelector('h3').textContent); }
      else { card.removeAttribute('tabindex'); card.removeAttribute('aria-label'); }
      card.style.transform = `translateX(${x}px)`;
      card.setAttribute('aria-current', i === index ? 'true' : 'false');
    });
  }
  function clearLayout() {
    active = -1;
    cards.forEach(card => {
      card.classList.remove('is-spine');
      card.removeAttribute('tabindex');
      card.removeAttribute('aria-label');
      card.style.transform = '';
      card.removeAttribute('aria-current');
    });
  }
  function onScroll() {
    if (!wide.matches || reduce) return;
    const rect = services.getBoundingClientRect();
    const travel = services.offsetHeight - window.innerHeight;
    const p = Math.min(1, Math.max(0, -rect.top / Math.max(1, travel)));
    layout(Math.min(cards.length - 1, Math.floor(p * cards.length)));
  }
  if (cards.length) {
    cards.forEach((card, i) => {
      const open = () => {
        if (!card.classList.contains('is-spine')) return;
        const travel = services.offsetHeight - window.innerHeight;
        const y = services.offsetTop + (i + 0.5) / cards.length * travel;
        window.scrollTo({ top: y, behavior: reduce ? 'auto' : 'smooth' });
      };
      card.addEventListener('click', open);
      card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
    const sync = () => (wide.matches && !reduce ? onScroll() : clearLayout());
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', () => { if (wide.matches && !reduce) layout(Math.max(0, active), true); });
    wide.addEventListener('change', sync);
    sync();
  }
})();
