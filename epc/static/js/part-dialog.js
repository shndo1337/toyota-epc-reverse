import { request } from './api.js';
import { displayNumber, formatCount, period } from './format.js';
import { $, html, setHtml } from './html.js';
import { state } from './state.js';

const APPLICATIONS_PER_PAGE = 10;
const VISIBLE_CATALOGS = 30;
const VISIBLE_RELATED = 100;
const CONDITION_TEXT = '1';

const detail = { controller: null, number: '', offset: 0 };

const dialog = () => $('#part-dialog');
const body = () => $('#part-body');

function startRequest() {
  detail.controller?.abort();
  detail.controller = new AbortController();
  return detail.controller.signal;
}

function showLoading() {
  setHtml(body(), html`<h2 id="part-title">Загружаем…</h2>`);
  if (!dialog().open) dialog().showModal();
}

function showError(error) {
  if (error.name === 'AbortError') return;
  setHtml(body(), html`<h2 id="part-title">Ошибка загрузки</h2><p class="error-box">${error.message}</p>`);
}

export function closeDetail() {
  detail.controller?.abort();
}

export function bindDialog() {
  $('#close-dialog').addEventListener('click', () => dialog().close());
  dialog().addEventListener('close', closeDetail);
  dialog().addEventListener('click', (event) => {
    if (event.target !== dialog()) return;
    const box = dialog().getBoundingClientRect();
    const outside = event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
    if (outside) dialog().close();
  });
}

function partSummary(part) {
  const names = [...new Set(part.names.map((name) => name.name || name.pnc))];
  const pncs = [...new Set(part.names.map((name) => name.pnc))];
  const price = part.list_price?.amount != null
    ? html`<p class="part-meta">Справочная цена JP: ${formatCount(part.list_price.amount)} JPY, издание 2025.01</p>`
    : '';
  const hiddenCatalogs = part.catalogs.length - VISIBLE_CATALOGS;
  const related = part.related_numbers.length
    ? html`<details class="related-numbers">
        <summary>Связанные номера и замены (${part.related_numbers.length})</summary>
        ${part.related_numbers.slice(0, VISIBLE_RELATED).map((item) => html`<p>
          <button type="button" class="part-link" data-related="${item.number}">${displayNumber(item.number)}</button>
          <small>${item.region}, ${item.source_type}</small>
        </p>`)}
      </details>`
    : '';
  const scope = state.vehicle
    ? 'Записи отфильтрованы по автомобилю: месяц, группа EPC, характеристики KPT/KIG и диапазоны кузова.'
    : 'Выбранные каталог и месяц ограничивают выдачу.';
  return html`<h2 id="part-title">${displayNumber(part.number)}</h2>
    <div class="part-names">${names.map((name, index) => html`${index ? html`<br>` : ''}${name}`)}</div>
    <div class="part-meta">PNC: ${pncs.join(', ')}<br>Каталогов: ${formatCount(part.catalogs.length)}</div>
    ${price}
    <div class="part-catalogs">
      ${part.catalogs.slice(0, VISIBLE_CATALOGS).map((catalog) => html`<span>${catalog.region} ${catalog.name} ${catalog.local_code}</span>`)}
      ${hiddenCatalogs > 0 ? html`<span>ещё ${hiddenCatalogs}</span>` : ''}
    </div>
    ${related}
    <p class="part-notice">${scope} Проверяйте дополнительные примечания EPC, цвет и опции.</p>
    <div class="applications-heading">
      <h3>Применяемость и условия</h3>
      <label for="production-month">Месяц выпуска <input id="production-month" type="month" min="1900-01" max="2099-12" value="${state.month}"></label>
    </div>
    <div id="application-list" aria-live="polite"></div>
    <div class="pagination dialog-pagination">
      <span id="application-page"></span>
      <div>
        <button type="button" id="application-previous" aria-label="Предыдущие записи">Назад</button>
        <button type="button" id="application-next" aria-label="Следующие записи">Вперёд</button>
      </div>
    </div>`;
}

export async function openPart(number) {
  const signal = startRequest();
  Object.assign(detail, { number, offset: 0 });
  showLoading();
  try {
    const part = await request(`/parts/${encodeURIComponent(number)}`, { signal });
    setHtml(body(), partSummary(part));
    $('#production-month').addEventListener('change', () => {
      detail.offset = 0;
      loadApplications();
    });
    $('#application-previous').addEventListener('click', () => {
      detail.offset -= APPLICATIONS_PER_PAGE;
      loadApplications();
    });
    $('#application-next').addEventListener('click', () => {
      detail.offset += APPLICATIONS_PER_PAGE;
      loadApplications();
    });
    for (const button of body().querySelectorAll('[data-related]')) {
      button.addEventListener('click', () => openPart(button.dataset.related));
    }
    await loadApplications();
  } catch (error) {
    showError(error);
  }
}

function groupTexts(texts) {
  const groups = new Map();
  for (const text of texts) {
    if (!groups.has(text.kind)) groups.set(text.kind, []);
    groups.get(text.kind).push(text.text);
  }
  return [...groups];
}

function applicationCard(application) {
  const texts = groupTexts(application.texts).map(([kind, lines]) => html`<p class="application-text">
    <small>${kind === CONDITION_TEXT ? 'Условия из EPC' : `Текст EPC, тип ${kind}`}</small>${lines}
  </p>`);
  return html`<article class="application-card">
    <div class="application-top">
      <span>${application.catalog_name}, ${application.catalog_code}</span>
      <span>${period(application.production_from, application.production_to)}</span>
    </div>
    <div class="application-info">PNC ${application.pnc}, количество: ${application.quantity}, группа EPC: ${application.source_group}</div>
    ${texts}
    <details class="source-details" data-source="${application.id}"><summary>Исходная запись</summary><pre>Загрузка…</pre></details>
  </article>`;
}

function describeSource(source) {
  const texts = source.texts.map((text) => `${text.source_offset}: [${text.kind}${text.sequence}] ${text.text}`);
  return [
    `Файл: ${source.source_path}`,
    `Смещение: ${source.source_offset} байт`,
    `Длина: ${source.record_size} байта`,
    `SHA-256: ${source.source_sha256}`,
    '',
    source.raw_record,
    '',
    ...texts,
  ].join('\n');
}

function bindSourceRecords(signal) {
  for (const element of body().querySelectorAll('[data-source]')) {
    element.addEventListener('toggle', async () => {
      if (!element.open || element.dataset.loaded) return;
      const output = element.querySelector('pre');
      try {
        const source = await request(`/applications/${encodeURIComponent(element.dataset.source)}`, { signal });
        output.textContent = describeSource(source);
        element.dataset.loaded = 'true';
      } catch (error) {
        if (error.name !== 'AbortError') output.textContent = error.message;
      }
    });
  }
}

async function loadApplications() {
  const signal = startRequest();
  const list = $('#application-list');
  const previous = $('#application-previous');
  const next = $('#application-next');
  list.textContent = 'Загружаем записи…';
  previous.disabled = true;
  next.disabled = true;
  try {
    const params = {
      limit: APPLICATIONS_PER_PAGE,
      offset: detail.offset,
      catalog_code: state.catalog,
      vehicle: state.vehicle,
      production_month: $('#production-month').value,
    };
    const page = await request(`/parts/${encodeURIComponent(detail.number)}/applications`, { params, signal });
    setHtml(list, page.items.length
      ? page.items.map(applicationCard)
      : html`<p class="part-meta">Подходящие записи не найдены.</p>`);
    $('#application-page').textContent = page.total
      ? `${detail.offset + 1}–${detail.offset + page.items.length} из ${formatCount(page.total)} записей`
      : '0 записей';
    previous.disabled = !detail.offset;
    next.disabled = !page.has_more;
    bindSourceRecords(signal);
  } catch (error) {
    if (error.name !== 'AbortError') setHtml(list, html`<p class="error-box">${error.message}</p>`);
  }
}

export async function openAccessory(id) {
  const signal = startRequest();
  showLoading();
  try {
    const item = await request(`/accessories/${encodeURIComponent(id)}`, { signal });
    const image = item.image_url
      ? html`<a href="${item.image_url}" target="_blank" rel="noopener"><img class="accessory-image" src="${item.image_url}" alt="${item.name}"></a>`
      : '';
    setHtml(body(), html`<h2 id="part-title">${item.number}</h2>
      <div class="part-names">${item.name}</div>
      <p class="part-meta">${item.title}<br>${period(item.production_from, item.production_to)}, ${item.destination}, количество: ${item.quantity}</p>
      <p class="part-notice">${item.notes}</p>
      <p class="part-meta">Модели: ${item.model_codes}</p>
      ${image}
      <details class="source-details"><summary>Исходный документ</summary><pre>${item.source_path}, строка ${item.source_row}\n${JSON.stringify(item.raw_fields, null, 2)}</pre></details>`);
  } catch (error) {
    showError(error);
  }
}
