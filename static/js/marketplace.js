// Mejora progresiva: todas las reglas y autorizaciones permanecen en el servidor.
document.addEventListener('click', (event) => {
  const action = event.target.closest('[data-confirm]');
  if (action && !window.confirm(action.dataset.confirm)) event.preventDefault();
});
