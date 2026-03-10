# Coding Guidelines

Standards and conventions for writing code in yanga-core.

## General Principles

- **Less is more** — be concise and question every implementation that looks too complicated; if there is a simpler way, use it.
- **Never nester** — maximum three indentation levels are allowed. Use early returns, guard clauses, and extraction into helper functions to keep nesting shallow. The third level should only be used when truly necessary.

## Data Structures

- **Use dataclasses for complex data structures**: prefer `dataclasses` over complex standard types (e.g. `tuple[list[str] | None, dict[str, str] | None]`) for function return values or internal data exchange to improve readability and extensibility.

## Type Hints

- Always include full type hints on functions, methods, public attributes, and constants.

## Style

- Prefer **pythonic** constructs: context managers, `pathlib`, comprehensions when clear, `enumerate`, `zip`, early returns, no over-nesting.
- Follow **SOLID**: single responsibility; prefer composition; program to interfaces (`Protocol`/ABC); inject dependencies.
- **Naming**: descriptive `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants. Avoid single-letter identifiers (including `i`, `j`, `a`, `b`) except in tight math helpers.
- Code should be **self-documenting**. Use docstrings only for public APIs or non-obvious rationale/constraints; avoid noisy inline comments.

## Error Handling

- Raise specific exceptions; never `except:` bare; add actionable context.

## Imports

- No wildcard imports; group stdlib / third-party / local; keep modules small and cohesive.

## Testability

- Pure functions where possible; pass dependencies, avoid globals/singletons.

## Testing

- Use `pytest`; keep the tests to a minimum; use parametrized tests when possible.
- Do not add useless comments — the tests shall be self-explanatory.
- Use fixtures to avoid code duplication; use `conftest.py` for shared fixtures. Use `tmp_path` for file system operations.

## Linting

- **Never suppress linter/type-checker warnings** by adding ignore rules to `pyproject.toml` or `# noqa` / `# type: ignore` comments. Always fix the underlying code instead.
