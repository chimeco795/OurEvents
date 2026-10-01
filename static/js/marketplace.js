// Mejora progresiva: todas las reglas y autorizaciones permanecen en el servidor.
document.addEventListener('click', (event) => {
  const action = event.target.closest('[data-confirm]');
  if (action && !window.confirm(action.dataset.confirm)) event.preventDefault();
});
document.querySelectorAll('[data-store-selector]').forEach(select=>select.addEventListener('change',()=>{window.location.assign(select.value)}));
document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('.account-menu[open]').forEach(menu=>{menu.removeAttribute('open');menu.querySelector('summary').focus()})});
document.addEventListener('click',event=>document.querySelectorAll('.account-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.removeAttribute('open')}));
