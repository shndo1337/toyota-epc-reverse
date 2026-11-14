import { request, requestAll } from './api.js';
import { formatCount } from './format.js';
import { $, html, setHtml } from './html.js';
import { catalogData, isAccessoryMode, state } from './state.js';

const POPULAR_CATALOGS = ['101510', '164520', '222230', '284590'];
const DEFAULT_REGION = 'EU';
const VISIBLE_CATALOGS = 120;
const VISIBLE_IMAGES = 8;

export async function loadCatalogs() {
  catalogData.catalogs = await requestAll('/catalogs');
  if (!chosenExists()) {
    state.catalog = '';
    state.figure = '';
  }
}

function chosenExists() {
  return catalogData.catalogs.some((catalog) => catalog.code === state.catalog);
}

function matchesSearch(catalog, needle) {
  return `${catalog.name} ${catalog.model_codes} ${catalog.local_code}`.toUpperCase().includes(needle);
}

export function renderCatalogs() {
  $('#region').value = state.region;
  $('#region').disabled = isAccessoryMode();
  $('#engine-filter').disabled = isAccessoryMode();

  const needle = $('#catalog-search').value.toUpperCase();
  const available = catalogData.catalogs.filter(
    (catalog) => (!state.region || catalog.region === state.region) && (!needle || matchesSearch(catalog, needle)),
  );
  $('#sidebar-count').textContent = formatCount(available.length);

  let visible = needle || state.region
    ? available.slice(0, VISIBLE_CATALOGS)
    : available.filter((catalog) => POPULAR_CATALOGS.includes(catalog.local_code) && catalog.region === DEFAULT_REGION);
  const chosen = catalogData.catalogs.find((catalog) => catalog.code === state.catalog);
  if (chosen && !visible.includes(chosen)) visible = [chosen, ...visible];

  setHtml($('#catalog-list'), visible.map((catalog) => {
    const active = catalog.code === state.catalog;
    return html`<button type="button" class="catalog-button ${active ? 'active' : ''}" data-catalog="${catalog.code}" aria-pressed="${active}">
      <span><strong>${catalog.name}</strong><small>${catalog.model_codes}<br>${catalog.region} ${catalog.local_code}</small></span>
    </button>`;
  }));
  $('#all-catalogs').classList.toggle('active', !state.catalog);
  $('#all-catalogs').setAttribute('aria-pressed', String(!state.catalog));
}

export async function loadFigures(onError) {
  const code = state.catalog;
  catalogData.figures = [];
  renderFigures();
  $('#figure-images').hidden = true;
  if (!code || isAccessoryMode()) return;
  try {
    const figures = await requestAll(`/catalogs/${encodeURIComponent(code)}/figures`);
    if (state.catalog !== code) return;
    catalogData.figures = figures;
    renderFigures();
    if (state.figure) await loadImages(onError);
  } catch (error) {
    onError(error);
  }
}

export function renderFigures() {
  const block = $('#figures-block');
  block.hidden = !state.catalog || isAccessoryMode();
  if (block.hidden) {
    $('#figure-list').replaceChildren();
    return;
  }
  const needle = $('#figure-search').value.trim().toUpperCase();
  const figures = catalogData.figures.filter((figure) => !needle || `${figure.code} ${figure.name}`.toUpperCase().includes(needle));
  const row = (code, name) => {
    const active = code === state.figure;
    return html`<li><button type="button" data-figure="${code}" class="${active ? 'active' : ''}" aria-pressed="${active}">
      <span class="figure-code num">${code}</span><span>${name}</span>
    </button></li>`;
  };
  setHtml($('#figure-list'), [row('', 'Все разделы'), ...figures.map((figure) => row(figure.code, figure.name))]);
}

export async function loadImages(onError) {
  const { catalog: code, figure } = state;
  const container = $('#figure-images');
  container.hidden = true;
  if (!code || !figure) return;
  try {
    const path = `/catalogs/${encodeURIComponent(code)}/figures/${encodeURIComponent(figure)}/images`;
    const { items } = await request(path, { params: { vehicle: state.vehicle, production_month: state.month } });
    if (state.catalog !== code || state.figure !== figure) return;
    const figures = items.slice(0, VISIBLE_IMAGES).map((image) => html`<figure>
      <a href="${image.diagram_url}" target="_blank" rel="noopener" title="Открыть схему в полном размере"><img src="${image.thumbnail_url}" alt="Эскиз ${image.image}" loading="lazy"></a>
      <figcaption>${image.image}</figcaption>
    </figure>`);
    setHtml(container, html`<span>Эскизы раздела</span>${figures}`);
    container.hidden = !items.length;
  } catch (error) {
    onError(error);
  }
}
