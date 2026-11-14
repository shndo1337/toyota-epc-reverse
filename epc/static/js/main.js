import { request } from './api.js';
import { loadCatalogs, loadFigures, loadImages, renderCatalogs, renderFigures } from './catalog-rail.js';
import { formatCount } from './format.js';
import { $ } from './html.js';
import { bindDialog, openAccessory, openPart } from './part-dialog.js';
import { renderTitle, search, setStatus } from './results.js';
import { goToNextPage, goToPreviousPage, resetPage, state } from './state.js';
import { clearVehicle, resolveVehicle } from './vehicle.js';

const TYPING_DELAY = 350;
const WIDE_LAYOUT = '(min-width: 60.01rem)';

let typingTimer;

const showError = (error) => setStatus(error.message, true);

function runSearch() {
  clearTimeout(typingTimer);
  return search();
}

function refreshCatalog() {
  renderCatalogs();
  renderTitle();
  loadFigures(showError);
  return runSearch();
}

function chooseCatalog(code, { keepVehicle = false } = {}) {
  if (!keepVehicle) clearVehicle();
  state.catalog = code;
  state.figure = '';
  resetPage();
  return refreshCatalog();
}

function chooseRegion(region) {
  Object.assign(state, { region, catalog: '', figure: '' });
  clearVehicle();
  resetPage();
  return refreshCatalog();
}

function chooseFigure(code) {
  state.figure = code;
  resetPage();
  renderFigures();
  loadImages(showError);
  return runSearch();
}

function dropVehicle() {
  clearVehicle();
  resetPage();
  return runSearch();
}

function applyInputs() {
  state.q = $('#search').value.trim();
  state.model = $('#model-filter').value.trim();
  state.engine = $('#engine-filter').value.trim();
  state.month = $('#month-filter').value;
  resetPage();
  if (state.figure) loadImages(showError);
  return runSearch();
}

function syncInputs() {
  $('#search').value = state.q;
  $('#model-filter').value = state.model;
  $('#engine-filter').value = state.engine;
  $('#month-filter').value = state.month;
}

function clearCondition(key) {
  if (key === 'vehicle') return dropVehicle();
  if (key === 'region') return chooseRegion('');
  if (key === 'catalog') return chooseCatalog('');
  if (key === 'figure') return chooseFigure('');
  state[key] = '';
  syncInputs();
  return applyInputs();
}

function clearFilters() {
  Object.assign(state, { model: '', engine: '', month: '', figure: '' });
  syncInputs();
  $('#figure-images').hidden = true;
  renderFigures();
  return dropVehicle();
}

const vehicleActions = {
  chooseCatalog,
  clearVehicle: dropVehicle,
  search: runSearch,
  refresh: refreshCatalog,
};

function onClick(selector, attribute, handler) {
  $(selector).addEventListener('click', (event) => {
    const target = event.target.closest(`[${attribute}]`);
    if (target) handler(target);
  });
}

function bindEvents() {
  $('#search-form').addEventListener('submit', (event) => {
    event.preventDefault();
    applyInputs();
  });
  for (const id of ['#search', '#model-filter', '#engine-filter']) {
    $(id).addEventListener('input', () => {
      clearTimeout(typingTimer);
      typingTimer = setTimeout(applyInputs, TYPING_DELAY);
    });
  }
  $('#month-filter').addEventListener('change', applyInputs);
  $('#clear-filters').addEventListener('click', clearFilters);
  $('#reset-search').addEventListener('click', () => {
    state.q = '';
    syncInputs();
    resetPage();
    runSearch();
  });
  for (const button of document.querySelectorAll('[data-example]')) {
    button.addEventListener('click', () => {
      state.q = button.dataset.example;
      syncInputs();
      resetPage();
      runSearch();
    });
  }
  $('#search-mode').addEventListener('change', (event) => {
    state.mode = event.target.value;
    resetPage();
    refreshCatalog();
  });

  $('#region').addEventListener('change', (event) => chooseRegion(event.target.value));
  $('#catalog-search').addEventListener('input', renderCatalogs);
  $('#all-catalogs').addEventListener('click', () => chooseCatalog(''));
  $('#figure-search').addEventListener('input', renderFigures);
  $('#vehicle-form').addEventListener('submit', (event) => {
    event.preventDefault();
    resolveVehicle(vehicleActions);
  });

  onClick('#catalog-list', 'data-catalog', (button) => chooseCatalog(button.dataset.catalog));
  onClick('#figure-list', 'data-figure', (button) => chooseFigure(button.dataset.figure));
  onClick('#context', 'data-clear', (button) => clearCondition(button.dataset.clear));
  onClick('#results', 'data-number', (button) => openPart(button.dataset.number));
  onClick('#results', 'data-accessory', (button) => openAccessory(button.dataset.accessory));

  $('#previous').addEventListener('click', () => {
    goToPreviousPage();
    runSearch();
  });
  $('#next').addEventListener('click', () => {
    goToNextPage();
    runSearch();
  });
  bindDialog();
}

function bindResponsiveRail() {
  const rail = $('.sidebar-disclosure');
  const wide = matchMedia(WIDE_LAYOUT);
  const sync = () => {
    if (wide.matches) rail.open = true;
    else if (!rail.dataset.touched) rail.open = false;
  };
  rail.addEventListener('toggle', () => {
    if (!wide.matches) rail.dataset.touched = 'true';
  });
  wide.addEventListener('change', sync);
  sync();
}

function showStatistics(stats) {
  $('#parts-count').textContent = formatCount(stats.counts.parts);
  $('#applications-count').textContent = formatCount(stats.counts.applications);
  $('#catalogs-count').textContent = formatCount(stats.counts.imported_catalogs);
  $('#vehicles-count').textContent = formatCount(stats.counts.vehicles);
  $('#database-status').textContent = 'База подключена';
}

async function start() {
  syncInputs();
  $('#vehicle-input').value = state.vehicle;
  $('#search-mode').value = state.mode;
  if (state.model || state.engine || state.month) $('.filters').open = true;
  bindEvents();
  bindResponsiveRail();
  try {
    const [stats] = await Promise.all([request('/stats'), loadCatalogs()]);
    showStatistics(stats);
    renderCatalogs();
    renderTitle();
    loadFigures(showError);
    if (state.vehicle) await resolveVehicle(vehicleActions, { restore: true });
    else await runSearch();
  } catch (error) {
    $('#database-status').textContent = 'База недоступна';
    $('.data-status').classList.add('is-down');
    showError(error);
    $('#page-description').textContent = 'Проверьте импорт каталога';
  }
}

start();
