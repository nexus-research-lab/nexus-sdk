from dataclasses import dataclass


@dataclass
class MemoryFile:
    path: str
    kind: str = "policy"
    writable: bool = False

    @classmethod
    def project(cls, path: str, kind: str = "policy", writable: bool = False) -> "MemoryFile":
        return cls(path=path, kind=kind, writable=writable)

    @classmethod
    def user(cls, path: str, kind: str = "long_term", writable: bool = False) -> "MemoryFile":
        return cls(path=path, kind=kind, writable=writable)
