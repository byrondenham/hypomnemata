from typing import MutableMapping, Iterator, Any


class MetaBag(MutableMapping[str, Any]):
    """
    Arbitrary namespaced keys, e.g.,
    - "core/title": "Covariant derivative"
    - "user/type": "math:definition"
    - "custom/difficulty": 3
    The core never *requires* any key besides Note.id existing in filename.
    """

    def __init__(self, initial: dict | None = None):
        self._d = dict(initial or {})

    # MutableMapping interface
    def __getitem__(self, k: str) -> Any:
        return self._d[k]

    def __setitem__(self, k: str, v: Any) -> None:
        self._d[k] = v

    def __delitem__(self, k: str) -> None:
        del self._d[k]

    def __iter__(self) -> Iterator[str]:
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    # Convenience
    def get_str(self, key: str, default: str | None = None) -> str | None:
        v = self._d.get(key, default)
        return v if isinstance(v, str) else default
