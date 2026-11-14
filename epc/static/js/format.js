const numbers = new Intl.NumberFormat('ru-RU');

export const formatCount = (value) => numbers.format(value);

export const displayNumber = (number) => (number.length === 10 ? `${number.slice(0, 5)}-${number.slice(5)}` : number);

export const period = (from, to) => `${from || 'нет даты'} / ${to || 'без конечной даты'}`;
