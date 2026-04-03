from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import List


@dataclass
class FilesystemPolicy:
    read_paths: List[str] = field(default_factory=list)
    write_paths: List[str] = field(default_factory=list)
    deny_paths: List[str] = field(default_factory=list)


@dataclass
class NetworkPolicy:
    allow_domains: List[str] = field(default_factory=list)
    deny_all_except_allowed: bool = False


@dataclass
class SandboxManager:
    default_provider: str = "container"
    filesystem_policy: FilesystemPolicy = field(default_factory=FilesystemPolicy)
    network_policy: NetworkPolicy = field(default_factory=NetworkPolicy)

    def is_path_allowed(self, path: str, write: bool = False) -> bool:
        if any(path.startswith(denied) for denied in self.filesystem_policy.deny_paths):
            return False
        allowed = self.filesystem_policy.write_paths if write else self.filesystem_policy.read_paths
        if not allowed:
            return True
        return any(path.startswith(candidate) for candidate in allowed)

    def is_domain_allowed(self, domain: str) -> bool:
        if not self.network_policy.allow_domains:
            return not self.network_policy.deny_all_except_allowed
        return any(fnmatch(domain, pattern) for pattern in self.network_policy.allow_domains)
