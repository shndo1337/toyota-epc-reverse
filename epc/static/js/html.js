const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

class SafeHtml {
  constructor(value) {
    this.value = value;
  }

  toString() {
    return this.value;
  }
}

function escape(value) {
  return String(value).replace(/[&<>"']/g, (char) => ENTITIES[char]);
}

function render(value) {
  if (value instanceof SafeHtml) return value.value;
  if (Array.isArray(value)) return value.map(render).join('');
  if (value === null || value === undefined || value === false) return '';
  return escape(value);
}

export function html(strings, ...values) {
  return new SafeHtml(strings.reduce((result, part, index) => result + render(values[index - 1]) + part));
}

export function setHtml(element, content) {
  element.innerHTML = render(content);
}

export const $ = (selector) => document.querySelector(selector);
