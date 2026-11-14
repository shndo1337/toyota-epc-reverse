const URL_KEYS = ['q', 'catalog', 'region', 'figure', 'vehicle', 'model', 'engine', 'month'];
export const PAGE_SIZE = 25;
export const ACCESSORIES = 'accessories';

function fromUrl() {
  const params = new URLSearchParams(location.search);
  const values = Object.fromEntries(URL_KEYS.map((key) => [key, params.get(key) || '']));
  return { ...values, mode: params.get('mode') === ACCESSORIES ? ACCESSORIES : 'parts' };
}

export const state = { ...fromUrl(), offset: 0, limit: PAGE_SIZE };

export const catalogData = { catalogs: [], figures: [] };

const pages = { previous: [], next: PAGE_SIZE };

export function resetPage() {
  state.offset = 0;
  pages.previous = [];
}

export function setNextOffset(offset) {
  pages.next = offset;
}

export function hasPreviousPage() {
  return pages.previous.length > 0;
}

export function goToNextPage() {
  pages.previous.push(state.offset);
  state.offset = pages.next;
}

export function goToPreviousPage() {
  state.offset = pages.previous.pop() ?? 0;
}

export function isAccessoryMode() {
  return state.mode === ACCESSORIES;
}

export function chosenCatalog() {
  return catalogData.catalogs.find((catalog) => catalog.code === state.catalog);
}

export function chosenFigure() {
  return catalogData.figures.find((figure) => figure.code === state.figure);
}

export function writeUrl() {
  const params = new URLSearchParams();
  for (const key of URL_KEYS) {
    if (state[key]) params.set(key, state[key]);
  }
  if (isAccessoryMode()) params.set('mode', ACCESSORIES);
  history.replaceState(null, '', params.size ? `/?${params}` : '/');
}
