import unittest

from rich_agent import ToolPermission, tool


@tool(
    description="Add two integers",
    permission=ToolPermission(require_approval=True, allowed_roles=["admin"]),
)
def add(a: int, b: int = 0) -> int:
    return a + b


class ToolingTests(unittest.TestCase):
    def test_schema_is_inferred_from_signature(self) -> None:
        self.assertEqual(add.name, "add")
        self.assertEqual(add.schema["properties"]["a"]["type"], "integer")
        self.assertEqual(add.schema["properties"]["b"]["type"], "integer")
        self.assertEqual(add.schema["required"], ["a"])

    def test_permission_metadata_is_preserved(self) -> None:
        self.assertTrue(add.permission.require_approval)
        self.assertEqual(add.permission.allowed_roles, ["admin"])


if __name__ == "__main__":
    unittest.main()
