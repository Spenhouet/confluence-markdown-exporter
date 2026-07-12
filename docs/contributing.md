---
title: Contributing
---

# Contributing

If you would like to contribute to `confluence-markdown-exporter`, please read the [contribution guideline](https://github.com/Spenhouet/confluence-markdown-exporter/blob/main/CONTRIBUTING.md) in the repository.

## Reporting issues

Use the [GitHub issue tracker](https://github.com/Spenhouet/confluence-markdown-exporter/issues). When reporting, include:

1. Your Confluence flavour and version (Cloud, Server, Data Center)
2. The exact command you ran
3. The full output with `cme config set export.log_level=DEBUG` enabled
4. A minimal page (if possible) reproducing the issue

## Docs site

The documentation site is authored as [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
and built with [Zensical](https://zensical.org/), then deployed to GitHub Pages.

- Sources live under `docs/` as plain Markdown; the site config is `mkdocs.yml`.
- Install the docs toolchain: `uv sync --group docs`.
- Local preview: `uv run zensical serve` (serves `http://127.0.0.1:8000`).
- Production build: `uv run zensical build --strict` (outputs to `site/`).

## License

This tool is an open source project released under the [MIT License](https://github.com/Spenhouet/confluence-markdown-exporter/blob/main/LICENSE).
