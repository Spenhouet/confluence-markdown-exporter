---
id: contributing
title: Contributing
sidebar_position: 7
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

The documentation site is built with [Docusaurus](https://docusaurus.io/) and deployed to GitHub Pages.

- Sources live under `docs/` in the repository as plain Markdown / MDX.
- Local preview: `npm ci && npm start` (serves `http://localhost:3000/confluence-markdown-exporter/`).
- Production build with all versions: `npm run build:versioned` then `npm run serve`.

### Versioning

Versioning is **driven by git release tags**. There are no `versioned_docs/` folders committed to the repo. At build time, `scripts/build-versions.mjs`:

1. Lists git tags matching `^\d+\.\d+\.\d+$` (the project's release pattern).
2. Filters to tags whose tree already contains a Docusaurus `docs/` + `sidebars.ts`.
3. Snapshots each eligible tag into `versioned_docs/version-<tag>/` by checking out that tag's docs and running `docusaurus docs:version`.
4. Builds with the newest tag set as the default version; HEAD becomes the `Next 🚧` (unreleased) version.

That means: cutting a new release tag automatically produces a new docs version on the next site build. Old versions cannot be edited after-the-fact; they are sourced directly from their git tag.

## License

This tool is an open source project released under the [MIT License](https://github.com/Spenhouet/confluence-markdown-exporter/blob/main/LICENSE).
