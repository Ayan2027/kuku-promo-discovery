"""Package the deliverables for submission.

The archive intentionally excludes the input pack, virtual environment and
git history. It *does* include raw_outputs/, which is required by the brief;
keep the archive private and share it only with the evaluator.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "submission"
STAGE = OUT / "Kuku_Problem1_Submission"
ARCHIVE = OUT / "Kuku_Problem1_Submission.zip"

INCLUDE_DIRS = [
    "src",
    "demo",
    "tests",
    "scripts",
    "docs",
    "prototype",
    "raw_outputs",
    ".streamlit",
]
INCLUDE_FILES = [
    "README.md",
    "app.py",
    "requirements.txt",
    "requirements-dev.txt",
    "Dockerfile",
    ".env.example",
    ".gitignore",
    "pytest.ini",
]

SUBMISSION_README = """# Kuku AI Generalist — Problem 1 submission

## Contents

- `docs/solution.pdf` — the required two-page solution document.
- `docs/solution.md` — editable source for the PDF.
- `raw_outputs/` — unedited machine outputs from the real-pack run.
- `prototype/index.html` — self-contained synthetic demo; open it directly.
- `app.py` — Streamlit human-triage prototype.
- `src/` — parser, discovery, scoring, validation, ranking, exports and CLI.
- `demo/` — synthetic demo data, safe to publish.
- `tests/` — 29 unit tests (`python -m pytest -q`).
- `README.md` — exact run steps, output schema, AI-tool disclosure and limitations.

## Run it

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m streamlit run app.py
```

The app falls back to `demo/` when real outputs are absent.

## Confidentiality

The Kuku input pack is **not** in this archive. `raw_outputs/` contains
screenplay excerpts; share the archive only with the evaluator, not publicly.
"""


def ignore_factory(directory, names):
    ignored = set()
    for name in names:
        if name == "__pycache__" or name == ".pytest_cache":
            ignored.add(name)
        if name.endswith(".pyc"):
            ignored.add(name)
    if Path(directory).name == "cache":
        ignored.update(names)
    return ignored


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    for directory in INCLUDE_DIRS:
        source = ROOT / directory
        if source.exists():
            shutil.copytree(
                source,
                STAGE / directory,
                ignore=ignore_factory,
            )

    # Demo input .txt files are reproducible from the generator; the ZIP is
    # enough and keeps the archive small.
    demo_input = STAGE / "demo" / "input"
    if demo_input.exists():
        for path in demo_input.glob("*.txt"):
            path.unlink()

    for filename in INCLUDE_FILES:
        source = ROOT / filename
        if source.exists():
            shutil.copy2(source, STAGE / filename)

    (STAGE / "SUBMISSION_README.md").write_text(
        SUBMISSION_README,
        encoding="utf-8",
    )

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in STAGE.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(STAGE))

    size_mb = ARCHIVE.stat().st_size / (1024 * 1024)
    print(f"Staged:  {STAGE}")
    print(f"Archive: {ARCHIVE} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
