import ast
from pathlib import Path

import pytest

PURE_MODULES = [
    "src/distro_event_tracker/events/models.py",
    "src/distro_event_tracker/events/scoring.py",
    "src/distro_event_tracker/dibs/models.py",
    "src/distro_event_tracker/dibs/persistence.py",
    "src/distro_event_tracker/dibs/summary.py",
]

COG_MODULES = [
    "src/distro_event_tracker/events/cog.py",
    "src/distro_event_tracker/dibs/cog.py",
]


@pytest.mark.parametrize("relative_path", PURE_MODULES)
def test_domain_modules_do_not_import_discord(relative_path):
    tree = ast.parse(Path(relative_path).read_text(encoding="utf-8"))
    imports = [
        node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import) and node.names
    ]
    imports.extend(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    assert not any(name == "discord" or name.startswith("discord.") for name in imports)


def test_importing_package_does_not_construct_bot():
    tree = ast.parse(Path("src/distro_event_tracker/__init__.py").read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert "bot" not in imports


@pytest.mark.parametrize("relative_path", COG_MODULES)
def test_cogs_do_not_import_compatibility_runtime(relative_path):
    tree = ast.parse(Path(relative_path).read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert "distro_event_tracker.bot" not in imports
