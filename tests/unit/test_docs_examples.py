from pathlib import Path


def test_required_docs_and_examples_exist():
    required = [
        "README.md",
        "AGENTS.md",
        "docs/ARCHITECTURE.md",
        "docs/CLI.md",
        "docs/PROJECT_FORMAT.md",
        "docs/LICENSE_AUDIT.md",
        "docs/ROADMAP.md",
        "examples/talking-head/project.json",
    ]
    missing = [path for path in required if not Path(path).exists()]
    assert missing == []


def test_readme_contains_first_video_commands():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "videoos doctor" in readme
    assert "videoos analyze" in readme
    assert "videoos edit" in readme
