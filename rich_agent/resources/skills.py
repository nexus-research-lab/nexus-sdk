from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class SkillMetadata:
    name: str
    description: str = ""
    version: Optional[str] = None
    allowed_tools: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    path: str = ""


def _parse_frontmatter(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    raw = parts[1]
    data: Dict[str, str] = {}
    current_key = None
    current_list: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            current_list.append(stripped[2:].strip())
            data[current_key] = ",".join(current_list)
            continue
        current_key = None
        current_list = []
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
        data[key] = value
        current_key = key
    return data


@dataclass
class SkillManager:
    platform_registry: Optional[str] = None
    namespace: Optional[str] = None

    def discover(self, sources: Iterable[str]) -> List[SkillMetadata]:
        found: List[SkillMetadata] = []
        for source in sources:
            root = Path(source).expanduser()
            if not root.exists():
                continue
            for skill_file in root.glob("*/SKILL.md"):
                meta = _parse_frontmatter(skill_file)
                found.append(
                    SkillMetadata(
                        name=meta.get("name", skill_file.parent.name),
                        description=meta.get("description", ""),
                        version=meta.get("version"),
                        allowed_tools=[item.strip() for item in meta.get("allowed-tools", "").split(",") if item.strip()],
                        tags=[item.strip() for item in meta.get("tags", "").split(",") if item.strip()],
                        path=str(skill_file.parent),
                    )
                )
        return found

    async def search(self, query: str, tags: Optional[List[str]] = None) -> List[SkillMetadata]:
        tags = tags or []
        return [
            skill
            for skill in self.discover([])
            if query.lower() in skill.name.lower()
            and (not tags or set(tags).issubset(set(skill.tags)))
        ]
