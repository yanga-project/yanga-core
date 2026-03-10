# AI Agent Development Guide

Rules and workflows for AI agents working on yanga-core. For project knowledge (architecture, concepts, API), see the [docs/](docs/) directory.

## Project Quick Reference

- **What it is**: core library for C/C++ software product line (SPL) engineering — not a standalone CLI
- **Architecture**: see [docs/explanation/architecture.md](docs/explanation/architecture.md)
- **Design decisions**: see [docs/explanation/design-decisions.md](docs/explanation/design-decisions.md)
- **Key concepts**: see [docs/explanation/concepts.md](docs/explanation/concepts.md)
- **API reference**: see [docs/reference/api.md](docs/reference/api.md)
- **Coding guidelines**: see [docs/reference/coding-guidelines.md](docs/reference/coding-guidelines.md)
- **Contributing (dev setup, tests, CI)**: see [docs/how-to/contributing.md](docs/how-to/contributing.md)

## Project Structure

```text
src/yanga_core/
├── commands/       # Reusable command classes (run, report, cppcheck, etc.)
├── domain/         # Core data models and business logic
├── docs/           # Sphinx documentation generation utilities
├── steps/          # Pipeline step implementations (KConfig, West, Poks, etc.)
└── ini.py          # Project-level configuration loader
```

## Mandatory Rules

### Plan Before Execution

**NEVER start making changes without presenting a plan first.**

1. **Create an implementation plan** documenting:
   - What files will be modified, created, or deleted
   - What changes will be made and why
   - How the changes will be verified
2. **Present the plan for user review** and ask for approval
3. **Wait for explicit approval** before proceeding with any file modifications
4. **Only after approval**, begin execution

Skipping this step is unacceptable.

### Never Change the Plan Without Approval

**NEVER deviate from the approved plan without asking the user first.** If the current approach hits a blocker (e.g., a tool doesn't work, a dependency is missing, a test fails unexpectedly), you MUST:

1. **Stop** — do not attempt an alternative approach on your own
2. **Report the problem** to the user with a clear description of what went wrong
3. **Propose alternatives** if you have ideas, but do NOT implement them
4. **Wait for explicit approval** before changing direction

This applies to all scope changes: switching libraries, replacing test targets, altering architecture, or any deviation from what was agreed upon. The user decides, not the agent.

## Verification

Run this to verify all changes:

```bash
pypeline run
```

See [docs/how-to/contributing.md](docs/how-to/contributing.md) for more commands and CI details.

## Definition of Done

Changes are NOT complete until:

- `pypeline run` executes with **zero failures**
- **All new functionality has tests** — never skip writing tests for new code
- Test coverage includes edge cases and error conditions
