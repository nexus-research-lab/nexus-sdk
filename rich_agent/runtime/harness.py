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
    policy_memories: Dict[str, str] = field(default_factory=dict)
    long_term_memories: Dict[str, str] = field(default_factory=dict)
    skill_summaries: List[str] = field(default_factory=list)

    def render_for_model(self) -> str:
        sections: List[str] = []
        if self.policy_memories:
            sections.append("Policy Memory:\n" + "\n\n".join(self.policy_memories.values()))
        if self.long_term_memories:
            sections.append("Long-Term Memory:\n" + "\n\n".join(self.long_term_memories.values()))
        if self.skill_summaries:
            sections.append("Visible Skills:\n- " + "\n- ".join(self.skill_summaries))
        if self.todos:
            rendered_todos = "\n".join("- %s [%s]" % (todo.title, todo.status) for todo in self.todos)
            sections.append("Todos:\n" + rendered_todos)
        return "\n\n".join(section for section in sections if section)


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
        policy_memories: Dict[str, str] = {}
        long_term_memories: Dict[str, str] = {}
        for memory_file in self.memory_files:
            try:
                content = self.workspace.read_text(memory_file.path)
                memories[memory_file.path] = content
                if memory_file.kind == "policy":
                    policy_memories[memory_file.path] = content
                else:
                    long_term_memories[memory_file.path] = content
            except FileNotFoundError:
                continue
        session_id = getattr(session, "session_id", "default")
        todos = await self.todo_store.list(session_id)
        skills = self.skill_manager.discover(self.skill_sources)
        return LoadedContext(
            memories=memories,
            skills=skills,
            todos=todos,
            policy_memories=policy_memories,
            long_term_memories=long_term_memories,
            skill_summaries=self.skill_manager.summarize(skills),
        )

    def compose_instructions(self, base_instructions: str, context: LoadedContext) -> str:
        additions = context.render_for_model()
        if not additions:
            return base_instructions
        return "%s\n\n%s" % (base_instructions, additions)
