import re
from dataclasses import dataclass

from epc.errors import InvalidRequestError

_PART_NUMBER = re.compile(r"[A-Z0-9]{10,12}")
_NUMBER_PREFIX = re.compile(r"[A-Z0-9]{1,12}")
_WORD = re.compile(r"[^\W_]+")
_NUMBER_PREFIX_END = "~"


@dataclass(frozen=True)
class TextQuery:
    number_prefix: str | None = None
    words: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.number_prefix is None and not self.words

    @property
    def number_range(self) -> tuple[str, str]:
        if self.number_prefix is None:
            raise ValueError("Not a part number query")
        return self.number_prefix, self.number_prefix + _NUMBER_PREFIX_END

    @property
    def fts_expression(self) -> str:
        return " AND ".join(f'"{word}"*' for word in self.words)


def normalize_number(value: str) -> str:
    return value.upper().replace("-", "").replace(" ", "")


def parse_part_number(value: str) -> str:
    number = normalize_number(value)
    if not _PART_NUMBER.fullmatch(number):
        raise InvalidRequestError("Expected a 10-12 character Toyota part number")
    return number


def display_number(number: str) -> str:
    return f"{number[:5]}-{number[5:]}" if len(number) == 10 else number


def parse_text_query(value: str) -> TextQuery | None:
    clean = value.strip()
    if not clean:
        return None
    normalized = normalize_number(clean)
    is_number = (
        _NUMBER_PREFIX.fullmatch(normalized)
        and any(char.isdigit() for char in normalized)
        and (normalized[0].isdigit() or " " not in clean)
    )
    if is_number:
        return TextQuery(number_prefix=normalized)
    return TextQuery(words=tuple(_WORD.findall(clean)))


def like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
