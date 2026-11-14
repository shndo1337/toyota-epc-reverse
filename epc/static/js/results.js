import { request } from './api.js';
import { formatCount } from './format.js';
import { $, html, setHtml } from './html.js';
import {
  chosenCatalog,
  chosenFigure,
  hasPreviousPage,
  isAccessoryMode,
  setNextOffset,
  state,
  writeUrl,
} from './state.js';

const FILTER_PARAMS = {
  catalog: 'catalog_code',
  region: 'region',
  figure: 'figure_code',
  vehicle: 'vehicle',
  model: 'model',
  engine: 'engine',
  month: 'production_month',
};

let controller;

export function setStatus(text, isError = false) {
  $('#status').textContent = text;
  $('#status').classList.toggle('error', isError);
}

export function renderTitle() {
  const catalog = chosenCatalog();
  const subject = isAccessoryMode() ? 'Аксессуары' : 'Детали';
  if (catalog) {
    $('#results-title').textContent = `${subject} ${catalog.name}`;
  } else {
    $('#results-title').textContent = isAccessoryMode() ? 'Аксессуары JPIO' : 'Все детали';
  }
}

function conditions() {
  const catalog = chosenCatalog();
  const figure = chosenFigure();
  return [
    ['vehicle', state.vehicle && `Автомобиль ${state.vehicle}`],
    ['region', state.region && !state.catalog && `Рынок ${state.region}`],
    ['catalog', catalog && `${catalog.region} ${catalog.name}`],
    ['figure', figure && `${figure.code} ${figure.name}`],
    ['model', state.model && `Модель ${state.model}`],
    ['engine', state.engine && `Двигатель ${state.engine}`],
    ['month', state.month && `Месяц ${state.month}`],
    ['q', state.q && `«${state.q}»`],
  ].filter(([, label]) => label);
}

function renderConditions() {
  setHtml($('#context'), conditions().map(([key, label]) => html`<button type="button" class="chip" data-clear="${key}">
    ${label}<span class="sr-only"> снять условие</span>
  </button>`));
}

function renderRows(items) {
  setHtml($('#results'), items.map((item) => {
    const target = item.accessory_id ? html`data-accessory="${item.accessory_id}"` : html`data-number="${item.number}"`;
    const catalogs = item.accessory_id ? 'JPIO' : formatCount(item.catalog_count);
    return html`<tr>
      <td><button type="button" class="part-link" ${target}>${item.display_number}</button></td>
      <td>${item.name || 'Без названия'}</td>
      <td><span class="catalog-number">${catalogs}</span></td>
      <td><button type="button" class="open-part" ${target} aria-label="Открыть ${item.display_number}">Открыть</button></td>
    </tr>`;
  }));
}

function describePage(data) {
  if (data.total_is_estimate) return `Показано: ${data.items.length}, отфильтровано по автомобилю / месяцу`;
  if (!data.total) return '0 деталей';
  const first = formatCount(state.offset + 1);
  const last = formatCount(state.offset + data.items.length);
  return `${first}–${last} из ${formatCount(data.total)} деталей`;
}

function describeTotal(data) {
  return data.total_is_estimate
    ? `до ${formatCount(data.total)} (до уточнения условий)`
    : `${formatCount(data.total)} найдено`;
}

function searchParams() {
  const params = { q: state.q, limit: state.limit, offset: state.offset };
  for (const [key, param] of Object.entries(FILTER_PARAMS)) params[param] = state[key];
  return params;
}

export async function search() {
  controller?.abort();
  controller = new AbortController();
  const { signal } = controller;
  const region = $('#results-region');

  renderConditions();
  setStatus('Ищем в каталоге…');
  region.setAttribute('aria-busy', 'true');
  $('#previous').disabled = true;
  $('#next').disabled = true;
  writeUrl();

  try {
    const data = await request(`/${state.mode}`, { params: searchParams(), signal });
    setNextOffset(data.next_offset ?? state.offset + state.limit);
    $('#result-total').textContent = describeTotal(data);
    renderRows(data.items);
    $('#empty-state').hidden = data.items.length > 0;
    region.hidden = data.items.length === 0;
    $('#page-description').textContent = describePage(data);
    $('#previous').disabled = !hasPreviousPage();
    $('#next').disabled = !data.has_more;
    setStatus('');
  } catch (error) {
    if (error.name === 'AbortError') return;
    setStatus(`Ошибка: ${error.message}`, true);
    $('#results').replaceChildren();
    $('#result-total').textContent = '';
    $('#page-description').textContent = 'Запрос не выполнен';
  } finally {
    if (!signal.aborted) region.setAttribute('aria-busy', 'false');
  }
}
