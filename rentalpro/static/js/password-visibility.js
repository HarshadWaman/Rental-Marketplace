document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-toggle-password]');
  if (!button) return;

  const input = button.closest('.password-input-group')?.querySelector('input');
  if (!input) return;

  const isVisible = input.type === 'password';
  input.type = isVisible ? 'text' : 'password';
  button.setAttribute('aria-pressed', String(isVisible));
  button.setAttribute('aria-label', isVisible ? 'Hide password' : 'Show password');
  button.querySelector('span').textContent = isVisible ? 'Hide' : 'Show';

  const icon = button.querySelector('i');
  if (icon) {
    icon.classList.toggle('bi-eye', !isVisible);
    icon.classList.toggle('bi-eye-slash', isVisible);
  }
});

document.addEventListener('change', (event) => {
  const toggle = event.target.closest('[data-theme-toggle]');
  if (!toggle) return;

  const theme = toggle.checked ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.bsTheme = theme;

  const label = document.querySelector('[data-theme-label]');
  if (label) label.textContent = toggle.checked ? 'Dark mode' : 'Light mode';

  const icon = document.querySelector('[data-theme-icon]');
  if (icon) {
    icon.classList.toggle('bi-moon-stars', toggle.checked);
    icon.classList.toggle('bi-sun', !toggle.checked);
  }
});
