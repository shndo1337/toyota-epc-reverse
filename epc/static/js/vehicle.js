import { request } from './api.js';
import { $, html, setHtml } from './html.js';
import { resetPage, state } from './state.js';

const VISIBLE_CANDIDATES = 8;

export function clearVehicle() {
  state.vehicle = '';
  $('#vehicle-result').replaceChildren();
}

function renderMatch(match, matches) {
  const vehicle = match.vehicle;
  const alternatives = matches.length > 1
    ? html`<label class="vehicle-market-label">Каталог автомобиля
        <select id="vehicle-match">${matches.map((option, index) => html`<option value="${index}" ${option.catalog_code === match.catalog_code ? html`selected` : ''}>
          ${option.region}, ${option.catalog_name}, ${option.model}, ${option.source_group}
        </option>`)}</select>
      </label>`
    : '';
  setHtml($('#vehicle-result'), html`<div class="vehicle-found">
    <div class="vehicle-id"><strong>${match.catalog_name}</strong><span>${vehicle.model}</span></div>
    <p class="vehicle-line"><span>${vehicle.production_month}</span><span>${match.engine}</span><span>${match.attributes}</span></p>
    <dl class="vehicle-specs">
      <div><dt>Кузов</dt><dd>${vehicle.frame_number}</dd></div>
      <div><dt>Цвет</dt><dd>${vehicle.color}</dd></div>
      <div><dt>Салон</dt><dd>${vehicle.trim}</dd></div>
    </dl>
    <small class="vehicle-source"><span>Точная запись EPC</span><span>${match.region}</span><span>${vehicle.source_path}</span></small>
    <button type="button" id="clear-vehicle">Снять подбор</button>
  </div>${alternatives}`);
}

function renderCandidates(result) {
  const title = result.resolution === 'catalog_candidates' ? 'Найдены каталоги по префиксу' : 'Автомобиль не найден';
  const market = state.region ? ' и выбранного рынка' : '';
  setHtml($('#vehicle-result'), html`<div class="vehicle-not-found">
    <strong>${title}</strong>
    <p>Точная запись автомобиля отсутствует для указанного номера${market}. Проверьте номер или выберите каталог вручную.</p>
    ${result.candidates.slice(0, VISIBLE_CANDIDATES).map((candidate) => html`<button type="button" data-candidate="${candidate.catalog_code}">
      ${candidate.region}, ${candidate.catalog_name}, ${candidate.model}
    </button>`)}
  </div>`);
}

export async function resolveVehicle(actions, { restore = false } = {}) {
  const identifier = $('#vehicle-input').value.trim().toUpperCase().replace(/\s/g, '');
  if (!identifier) return;
  const submit = $('#vehicle-submit');
  submit.disabled = true;
  $('#vehicle-result').textContent = 'Ищем автомобиль в EPC…';
  try {
    const result = await request('/vehicles/resolve', { params: { identifier, region: state.region } });
    if (result.resolution === 'exact') {
      const match = result.matches.find((item) => item.catalog_code === state.catalog) || result.matches[0];
      Object.assign(state, { vehicle: identifier, region: match.region, catalog: match.catalog_code, figure: '' });
      resetPage();
      renderMatch(match, result.matches);
      $('#clear-vehicle').addEventListener('click', actions.clearVehicle);
      $('#vehicle-match')?.addEventListener('change', (event) => {
        const chosen = result.matches[Number(event.target.value)];
        state.region = chosen.region;
        actions.chooseCatalog(chosen.catalog_code, { keepVehicle: true });
      });
      await actions.refresh();
      return;
    }
    state.vehicle = '';
    resetPage();
    renderCandidates(result);
    for (const button of document.querySelectorAll('[data-candidate]')) {
      button.addEventListener('click', () => actions.chooseCatalog(button.dataset.candidate));
    }
    if (!restore) await actions.search();
  } catch (error) {
    setHtml($('#vehicle-result'), html`<p class="error-box">${error.message}</p>`);
  } finally {
    submit.disabled = false;
  }
}
