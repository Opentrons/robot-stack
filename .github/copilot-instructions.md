# GitHub Copilot Instructions

## 🧠 Repository Purpose

This repository provides a Python CLI ish toolset to evaluate, tag, and trigger builds across multiple repositories that make up the Opentrons robot software stack. These tools help the user analyze changes in all of teh repositories and then gather and present the information needed to make decisions about what commits needs tagged in each repository and generates a report for each build.

- **Flex robots** using `oe-core`, `ot3-firmware`, and `opentrons`
- **OT-2 robots** using `opentrons` and `buildroot`

The system supports internal and external release channels, and this tool helps enforce consistency and correctness before triggering final operating system builds.

---

## 🛠️ Development Standards

### ✅ Language & Version

- Python **3.13**
- Static typing required throughout (`mypy` compliance)
- Use PEP8 naming and structure guidelines

### 🎨 Formatting & Style

- Use [`black`](https://github.com/psf/black) for formatting
- Use [`ruff`](https://github.com/astral-sh/ruff) for linting and code quality and import sorting
- Avoid trailing semicolons
- Prefer `async` / `await` where appropriate
- Follow "clean code" principles (readability > cleverness)

### 📄 Code Commenting & Structure

- Every function and class should include:
  - A **first meaningful comment or docstring**, following [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
  - Type hints for all parameters and return values
- Use descriptive variable and function names
- Prefer composition over inheritance unless there's a clear hierarchy

---

## 🤖 Tips for Copilot

- Suggest command-line utilities using [`argparse`](https://docs.python.org/3/library/argparse.html) or [`typer`](https://github.com/tiangolo/typer)
- Use the `subprocess` module for shell command execution, with safety in mind (`check=True`, avoid `shell=True`)
- Use `rich` for beautiful terminal output (tables, logs, progress bars)

---

## ✨ Miscellaneous

- Use `Path` from `pathlib`, not raw strings or `os.path`
- Default to immutability where possible (e.g., tuples, frozen dataclasses)
- CLI tools should include a `--dry-run` mode for safety

---
