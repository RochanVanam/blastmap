# Blastmap

**See your codebase the way your compiler does.**

Blastmap maps any Python repository into an interactive dependency graph — every file, every import, every connection — in a single command. Built for engineers who need to understand large codebases fast.

---

## Install

```bash
pip install blastmap
```

---

## Usage

Scan the current directory:

```bash
blastmap scan
```

Scan any repo:

```bash
blastmap scan /path/to/repo
```

Custom output file:

```bash
blastmap scan /path/to/repo --output my-graph.html
```

Then open the generated HTML file in your browser.

---

## Features

- Zero config — point it at any Python repo and it works
- Handles both standard and `src/` layout repos automatically
- Respects `.gitignore` — no noise from virtual environments or build artifacts
- Interactive graph — zoom, pan, drag nodes
- Click any node to see its parents and children instantly
- Search bar — find any file or module without hunting through the graph
- Nodes sized by dependents — the most critical files are visually largest
- Custom tooltips — filename, path, and dependent count on hover

---

## How It Works

Blastmap uses Python's built-in `ast` module to parse every `.py` file in your repo and extract import relationships. It then builds a directed graph with `networkx` and renders it as a self-contained interactive HTML file using `pyvis`.

No servers. No accounts. No data leaves your machine.

---

## Examples

| Repo | Files | Edges | Most Critical File |
|------|-------|-------|--------------------|
| Flask | 84 | 71 | `flask/__init__.py` (44 dependents) |
| Scrapy | 446 | 1,794 | `scrapy/__init__.py` (191 dependents) |
| Django | 2,911 | 7,585 | `django/test/__init__.py` (790 dependents) |

---

## Roadmap

- JavaScript / TypeScript support
- Java and Go support
- Blast-radius command — highlight everything affected by a given file
- VS Code extension

---

## License

MIT