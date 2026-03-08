---
sd_hide_title: true
---

# yanga-core

**yanga-core** is a build-system-agnostic framework for engineering Software Product Lines (SPL). It provides the domain model, pipeline orchestration, project discovery, and reusable pipeline steps — without coupling to any specific build backend (CMake, Ninja, Make, etc.).

Use yanga-core to:

- Define **variants**, **components**, and **platforms** for your product line
- Orchestrate a **configurable pipeline** of build steps
- Manage **feature models** with KConfig
- Acquire **external dependencies** (West, Poks)
- Generate **report configurations** for documentation pipelines

---

::::{grid} 1 2 2 4
:gutter: 1 1 1 2

:::{grid-item-card} Tutorials
:link: tutorials/index
:link-type: doc

Learn yanga-core step-by-step.

+++
[Start learning &raquo;](tutorials/index)
:::

:::{grid-item-card} How-to Guides
:link: how-to/index
:link-type: doc

Task-oriented guides for specific goals.

+++
[Find solutions &raquo;](how-to/index)
:::

:::{grid-item-card} Reference
:link: reference/index
:link-type: doc

Technical reference for configuration, pipeline, and API.

+++
[Browse reference &raquo;](reference/index)
:::

:::{grid-item-card} Explanation
:link: explanation/index
:link-type: doc

Understand the concepts and design decisions.

+++
[Learn why &raquo;](explanation/index)
:::

::::

---

```{toctree}
:hidden:
:maxdepth: 2

tutorials/index
how-to/index
reference/index
explanation/index
```
