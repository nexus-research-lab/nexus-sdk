from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..control.approvals import ApprovalHandler
from ..resources.memory import MemoryFile
from .sandbox import SandboxManager
from ..resources.skills import SkillManager, SkillMetadata
from ..resources.todos import SessionTodoStore, TodoItem
from .workspace import Workspace


@dataclass
class LoadedContext:
    memories: Dict[str, str] = field(default_factory=dict)
    skills: List[SkillMetadata] = field(default_factory=list)
    todos: List[TodoItem] = field(default_factory=list)


@dataclass
class AgentHarness:
    workspace: Workspace
    memory_files: List[MemoryFile] = field(default_factory=list)
    skill_sources: List[str] = field(default_factory=list)
    todo_store: SessionTodoStore = field(default_factory=SessionTodoStore)
    sandbox: SandboxManager = field(default_factory=SandboxManager)
    approval_handler: Optional[ApprovalHandler] = None
    skill_manager: SkillManager = field(default_factory=SkillManager)

    async def load_context(self, session: Optional[object] = None) -> LoadedContext:
        memories: Dict[str, str] = {}
        for memory_file in self.memory_files:
            try:
                memories[memory_file.path] = self.workspace.read_text(memory_file.path)
            except FileNotFoundError:
                continue
        session_id = getattr(session, "session_id", "default")
        todos = await self.todo_store.list(session_id)
        skills = self.skill_manager.discover(self.skill_sources)
        return LoadedContext(memories=memories, skills=skills, todos=todos)
