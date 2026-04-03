from dataclasses import dataclass
from pathlib import Path


@dataclass
class Workspace:
    backend: str
    root: str
    mode: str = "workspace_write"

    @classmethod
    def local(cls, path: str, mode: str = "workspace_write") -> "Workspace":
        return cls(backend="local_fs", root=str(Path(path).expanduser().resolve()), mode=mode)

    @classmethod
    def memory(cls, root: str = "memory://workspace", mode: str = "workspace_write") -> "Workspace":
        return cls(backend="memory_fs", root=root, mode=mode)

    def resolve_path(self, relative_path: str) -> Path:
        if self.backend != "local_fs":
            raise ValueError("Path resolution only supports local_fs workspaces in v0.")
        return Path(self.root).joinpath(relative_path).resolve()

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        return self.resolve_path(relative_path).read_text(encoding=encoding)

    def write_text(self, relative_path: str, content: str, encoding: str = "utf-8") -> Path:
        target = self.resolve_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        return target
