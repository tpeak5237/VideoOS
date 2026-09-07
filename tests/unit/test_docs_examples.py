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


def test_rendering_docs_describe_default_and_explicit_output_boundaries():
    rendering = Path("docs/RENDERING.md").read_text(encoding="utf-8")

    assert "Default outputs stay in the project `renders/` directory" in rendering
    assert "explicit `--output` paths use their own validated parent directory" in rendering
    assert "not constrained to the project directory" in rendering


def test_license_audit_covers_declared_setuptools_build_dependency():
    audit = Path("docs/LICENSE_AUDIT.md").read_text(encoding="utf-8")

    assert "setuptools / MIT" in audit
    assert "https://github.com/pypa/setuptools" in audit
