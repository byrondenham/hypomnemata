import secrets

from ..core.ports import IdGenerator


class HexId(IdGenerator):
    def __init__(self, nbytes: int = 4):  # 4 bytes -> 8 hex chars
        self.nbytes = nbytes

    def new_id(self) -> str:
        return secrets.token_hex(self.nbytes)[:7]
