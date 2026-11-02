/* SQSY themes and the sidebar, as in Jackil and Vigil. The saved theme is
   applied before first paint by the inline script in base.html. */
const THEMES = ['dark', 'light', 'river', 'ink'];
const THEME_LABELS = { dark: 'Dark', light: 'Paper', river: 'River', ink: 'Ink' };

function setTheme(mode) {
  if (!THEMES.includes(mode)) mode = 'dark';
  document.documentElement.setAttribute('data-theme', mode);
  try { localStorage.setItem('sqsy-theme', mode); } catch (e) {}
  const toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.dataset.tip = 'Theme: ' + THEME_LABELS[mode];
    const label = toggle.querySelector('.sidebar-label');
    if (label) label.textContent = 'Theme: ' + THEME_LABELS[mode];
  }
}

function toggleTheme() {
  const root = document.documentElement;
  root.classList.add('theme-shift');
  clearTimeout(toggleTheme._t);
  toggleTheme._t = setTimeout(() => root.classList.remove('theme-shift'), 450);
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  setTheme(THEMES[(THEMES.indexOf(current) + 1) % THEMES.length]);
}

function toggleSidebar() {
  const expanded = document.documentElement.getAttribute('data-sidebar') !== 'expanded';
  if (expanded) document.documentElement.setAttribute('data-sidebar', 'expanded');
  else document.documentElement.removeAttribute('data-sidebar');
  try { localStorage.setItem('sqsy-sidebar', expanded ? 'expanded' : 'collapsed'); } catch (e) {}
  _applySidebarToggle(expanded);
}

function _applySidebarToggle(expanded) {
  const btn = document.getElementById('sidebar-toggle');
  if (!btn) return;
  const words = expanded ? 'Hide page names' : 'Show page names';
  btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  btn.setAttribute('aria-label', words);
  btn.dataset.tip = words;
  const label = btn.querySelector('.sidebar-label');
  if (label) label.textContent = expanded ? 'Collapse' : 'Expand';
}

const _reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Stat figures count up from zero once, when the page opens.
function countUp(el) {
  const target = parseInt(el.textContent.replace(/,/g, ''), 10);
  if (!/^\s*[\d,]+\s*$/.test(el.textContent) || !target || _reducedMotion()) return;
  const start = performance.now(), dur = 700;
  const step = (now) => {
    const t = Math.min(1, (now - start) / dur);
    el.textContent = Math.round(target * (1 - Math.pow(2, -10 * t))).toLocaleString();
    if (t < 1) requestAnimationFrame(step); else el.textContent = target.toLocaleString();
  };
  el.textContent = '0';
  requestAnimationFrame(step);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.stat .n').forEach(countUp);
  // Each icon's tooltip doubles as its label when the sidebar is expanded.
  document.querySelectorAll('.sidebar .sidebar-icon[data-tip]').forEach((icon) => {
    if (icon.querySelector('.sidebar-label')) return;
    const label = document.createElement('span');
    label.className = 'sidebar-label';
    label.textContent = icon.dataset.tip;
    icon.appendChild(label);
  });
  _applySidebarToggle(document.documentElement.getAttribute('data-sidebar') === 'expanded');
  setTheme(document.documentElement.getAttribute('data-theme') || 'dark');
  const bind = (el, fn) => {
    if (!el) return;
    el.addEventListener('click', fn);
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(); }
    });
  };
  bind(document.getElementById('theme-toggle'), toggleTheme);
  bind(document.getElementById('sidebar-toggle'), toggleSidebar);
});
