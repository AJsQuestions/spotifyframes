from __future__ import annotations
from typing import Iterator, TypeVar

T = TypeVar("T")

def chunks(xs: list[T], n: int) -> Iterator[list[T]]:
    for i in range(0, len(xs), n):
        yield xs[i:i+n]
