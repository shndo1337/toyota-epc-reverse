const API_ROOT = '/api/v1';
const FALLBACK_MESSAGE = 'Проверьте параметры запроса.';

export async function request(path, { params = {}, signal } = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== '' && value !== null && value !== undefined) query.set(key, value);
  }
  const url = `${API_ROOT}${path}${query.size ? `?${query}` : ''}`;
  const response = await fetch(url, { signal });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : FALLBACK_MESSAGE);
  return data;
}

export async function requestAll(path, pageSize = 100) {
  const items = [];
  let page;
  do {
    page = await request(path, { params: { limit: pageSize, offset: items.length } });
    items.push(...page.items);
  } while (page.has_more);
  return items;
}
