# Python Project Starter

This folder is a reusable starter for new Python repositories.

## Replace These Placeholders

- `your-project-name`: distribution / project name shown in packaging and CLI
- `your_package_name`: importable Python package under `src/`
- `Your Name`: package author
- `you@example.com`: author email
- README description text

## Intended Defaults

- `src/` layout
- `setuptools` build backend
- tracked `.env.defaults`, ignored local `.env`
- pytest, ruff, and mypy config in `pyproject.toml`
- minimal CLI entrypoint so every new project starts runnable

## First-Project Checklist

1. Copy this folder's contents into the root of the new repo.
2. Rename `src/your_package_name/` to the real package name.
3. Search-replace `your-project-name` and `your_package_name`.
4. Update dependencies in `pyproject.toml`.
5. Copy `.env.defaults` to `.env` only if you need local overrides.
6. Add a license and CI workflow if the project needs them.

## Optional Simplifications

- If the project has no CLI, remove `[project.scripts]`, `cli.py`, and `__main__.py`.
- If the project is library-only, trim the README run section.
- If you prefer another linter/formatter, swap the `ruff` section out in `pyproject.toml`.
