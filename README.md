<p align="center">
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter"><img src="https://raw.githubusercontent.com/Spenhouet/confluence-markdown-exporter/b8caaba935eea7e7017b887c86a740cb7bf99708/logo.png" alt="confluence-markdown-exporter"></a>
</p>
<p align="center">
    <em>The confluence-markdown-exporter exports Confluence pages in Markdown format. This exporter helps in migrating content from Confluence to platforms that support Markdown e.g. Obsidian, Gollum, Azure DevOps (ADO), Foam, Dendron and more.</em>
</p>
<p align="center">
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/ci.yml"><img src="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/ci.yml/badge.svg" alt="Test, Lint and Build"></a>
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/release.yml"><img src="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/release.yml/badge.svg" alt="Build and publish to PyPI"></a>
  <a href="https://pypi.org/project/confluence-markdown-exporter" target="_blank">
    <img src="https://img.shields.io/pypi/v/confluence-markdown-exporter?color=%2334D058&label=PyPI%20package" alt="Package version">
   </a>
</p>

## Features

- Converts Confluence pages to Markdown format.
- Uses the Atlassian API to export individual pages, pages including children, and whole spaces.
- Supports various Confluence elements such as headings, paragraphs, lists, tables, and more.
- Retains formatting such as bold, italic, and underline.
- Converts Confluence macros to equivalent Markdown syntax where possible.
- Handles images and attachments by linking them appropriately in the Markdown output.
- Supports extended Markdown features like tasks, alerts, and front matter.
- Skips unchanged pages by default — only re-exports pages that have changed since the last run.
- Supports Confluence add-ons: [draw.io](https://marketplace.atlassian.com/apps/1210933/draw-io-diagrams-uml-bpmn-aws-erd-flowcharts), [PlantUML](https://marketplace.atlassian.com/apps/1222993/flowchart-plantuml-diagrams-for-confluence), [Markdown Extensions](https://marketplace.atlassian.com/apps/1215703/markdown-extensions-for-confluence)

## Supported Markdown Elements

- **Headings**: Converts Confluence headings to Markdown headings.
- **Paragraphs**: Converts Confluence paragraphs to Markdown paragraphs.
- **Lists**: Supports both ordered and unordered lists.
- **Tables**: Converts Confluence tables to Markdown tables.
- **Formatting**: Supports bold, italic, and underline text.
- **Links**: Converts Confluence links to Markdown links.
- **Images**: Converts Confluence images to Markdown images with appropriate links.
- **Code Blocks**: Converts Confluence code blocks to Markdown code blocks.
- **Tasks**: Converts Confluence tasks to Markdown task lists.
- **Alerts**: Converts Confluence info panels to Markdown alert blocks.
- **Front Matter**: Adds front matter to the Markdown files for metadata like page properties and page labels.
- **Mermaid**: Converts Mermaid diagrams embedded in draw.io diagrams to Mermaid code blocks.
- **PlantUML**: Converts PlantUML diagrams to Markdown code blocks.

## Usage

To use the confluence-markdown-exporter, follow these steps:

### 1. Installation

Install python package via pip.

```sh
pip install confluence-markdown-exporter
```

### 2. Exporting

Run the exporter with the desired Confluence page ID or space key. Execute the console application by typing `confluence-markdown-exporter` and one of the commands `pages`, `pages-with-descendants`, `spaces`, `all-spaces` or `config`. If a command is unclear, you can always add `--help` to get additional information.

#### 2.1. Export Page(s)

Export Confluence page(s) by URL(s):

```sh
cme pages <page-url> --output-path <output path e.g. ./output_path/>
```

Supported page URL formats:
- Confluence Cloud: <https://company.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Page+Title>
- Confluence Server (long): <https://company.atlassian.net/display/SPACEKEY/Page+Title>
- Confluence Server (short): <https://company.atlassian.net/SPACEKEY/Page+Title>

#### 2.2. Export Page(s) with Descendants

Export Confluence page(s) and all their descendant pages by page URL(s):

```sh
cme pages-with-descendants <page-url> --output-path <output path e.g. ./output_path/>
```

#### 2.3. Export Space(s)

Export all Confluence pages of Spaces by URLs:

```sh
cme spaces <space-url> --output-path <output path e.g. ./output_path/>
```

Supported space URL formats:
- Confluence Cloud: <https://company.atlassian.net/wiki/spaces/SPACEKEY>
- Confluence Server (long): <https://company.atlassian.net/display/SPACEKEY>
- Confluence Server (short): <https://company.atlassian.net/SPACEKEY>

#### 2.4. Export all Spaces of Organization(s)

Export all Confluence pages across all spaces of organization(s) by URL(s):

```sh
cme orgs --output-path <output path e.g. ./output_path/>
```

### 3. Output

The exported Markdown file(s) will be saved in the specified `output` directory e.g.:

```sh
output_path/
└── MYSPACE/
   ├── MYSPACE.md
   └── MYSPACE/
      ├── My Confluence Page.md
      └── My Confluence Page/
            ├── My nested Confluence Page.md
            └── Another one.md
```

## Configuration

All configuration and authentication is stored in a single JSON file managed by the application. You do not need to manually edit this file.

### Interactive Configuration

To interactively view and change configuration, run:

```sh
cme config
```

This will open a menu where you can:

- See all config options and their current values
- Select a config to change (including authentication)
- Reset all config to defaults
- Navigate directly to any config section (e.g. `auth.confluence`)

To display the current configuration as YAML without opening the interactive menu:

```sh
cme config --show
```

To jump directly to a specific config section:

```sh
cme config --jump-to auth.confluence
```

### Available Configuration Options

| Key                                   | Description                                                                                                           | Default                                                             |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| export.log_level                      | Controls output verbosity: `DEBUG` (every step), `INFO` (key milestones), `WARNING` (warnings/errors only), `ERROR` (errors only). | INFO                                                                |
| export.output_path                    | The directory where all exported files and folders will be written. Used as the base for relative and absolute links. | ./ (current working directory)                                      |
| export.page_href                      | How to generate links to pages in Markdown. Options: "relative" (default) or "absolute".                              | relative                                                            |
| export.page_path                      | Path template for exported pages                                                                                      | {space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md     |
| export.attachment_href                | How to generate links to attachments in Markdown. Options: "relative" (default) or "absolute".                        | relative                                                            |
| export.attachment_path                | Path template for attachments                                                                                         | {space_name}/attachments/{attachment_file_id}{attachment_extension} |
| export.attachment_export_all          | Export all attachments, not only those referenced by a page. Note: exporting large or many attachments increases export time. | False                                                          |
| export.page_breadcrumbs               | Whether to include breadcrumb links at the top of the page.                                                           | True                                                                |
| export.filename_encoding              | Character mapping for filename encoding.                                                                              | Default mappings for forbidden characters.                          |
| export.filename_length                | Maximum length of filenames.                                                                                          | 255                                                                 |
| export.include_document_title         | Whether to include the document title in the exported markdown file.                                                  | True                                                                |
| export.enable_jira_enrichment         | Fetch Jira issue data to enrich Confluence pages. When enabled, Jira issue links include the issue summary. Requires Jira auth to be configured. | True                                     |
| export.skip_unchanged                 | Skip exporting pages that have not changed since last export. Uses a lockfile to track page versions.                 | True                                                                |
| export.cleanup_stale                  | After export, delete local files for pages removed from Confluence or whose export path has changed.                  | True                                                                |
| export.lockfile_name                  | Name of the lock file used to track exported pages.                                                                   | confluence-lock.json                                                |
| export.existence_check_batch_size     | Number of page IDs per batch when checking page existence during cleanup. Capped at 25 for self-hosted (CQL).         | 250                                                                 |
| connection_config.backoff_and_retry   | Enable automatic retry with exponential backoff                                                                       | True                                                                |
| connection_config.backoff_factor      | Multiplier for exponential backoff                                                                                    | 2                                                                   |
| connection_config.max_backoff_seconds | Maximum seconds to wait between retries                                                                               | 60                                                                  |
| connection_config.max_backoff_retries | Maximum number of retry attempts                                                                                      | 5                                                                   |
| connection_config.retry_status_codes  | HTTP status codes that trigger a retry                                                                                | \[413, 429, 502, 503, 504\]                                         |
| connection_config.timeout             | Timeout in seconds for API requests. Prevents hanging on slow or unresponsive servers.                                | 30                                                                  |
| connection_config.verify_ssl          | Whether to verify SSL certificates for HTTPS requests.                                                                | True                                                                |
| connection_config.use_v2_api          | Enable Confluence REST API v2 endpoints. Supported on Atlassian Cloud and Data Center 8+. Disable for self-hosted Server instances. | False                                                    |
| connection_config.max_workers         | Maximum number of parallel workers for page export. Set to `1` for serial/debug mode. Higher values improve performance but may hit API rate limits. | 20                                          |
| auth.confluence.url                   | Confluence instance URL                                                                                               | ""                                                                  |
| auth.confluence.username              | Confluence username/email                                                                                             | ""                                                                  |
| auth.confluence.api_token             | Confluence API token                                                                                                  | ""                                                                  |
| auth.confluence.pat                   | Confluence Personal Access Token                                                                                      | ""                                                                  |
| auth.jira.url                         | Jira instance URL                                                                                                     | ""                                                                  |
| auth.jira.username                    | Jira username/email                                                                                                   | ""                                                                  |
| auth.jira.api_token                   | Jira API token                                                                                                        | ""                                                                  |
| auth.jira.pat                         | Jira Personal Access Token                                                                                            | ""                                                                  |

You can always view and change the current config with the interactive menu above.

### Configuration for Target Systems

Some platforms have specific requirements for Markdown formatting, file structure, or metadata. You can adjust the export configuration to optimize output for your target system. Below are some common examples:

#### Obsidian

- **Document Title**: Obsidian already displays the document title. Ensure `export.include_document_title` is `False` so the documented title is not redundant.
- **Breadcrumbs**: Obsidian already displays page breadcrumbs. Ensure `export.breadcrumbs` is `False` so the breadcrumbs are not redundant.

#### Azure DevOps (ADO) Wikis

- **Absolute Attachment Links**: Ensure `export.attachment_href` is set to `absolute`.
- **Attachment Path Template**: Set `export.attachment_path` to `.attachments/{attachment_file_id}{attachment_extension}` so ADO Wiki can find attachments.
- **Filename sanitizing**:
  - Set `export.filename_encoding` to `" ":"-","\"":"%22","*":"%2A","-":"%2D",":":"%3A","<":"%3C",">":"%3E","?":"%3F","|":"%7C","\\":"_","#":"_","/":"_","\u0000":"_"`
    for ADO compatibility (spaces become `-`, dashes become `%2D`, and forbidden characters become `_`)
  - Set `export.filename_length` to `200`

### Custom Config File Location

By default, configuration is stored in a platform-specific application directory. You can override the config file location by setting the `CME_CONFIG_PATH` environment variable to the desired file path. If set, the application will read and write config from this file instead. Example:

```sh
export CME_CONFIG_PATH=/path/to/your/custom_config.json
```

### Running in CI / Non-Interactive Environments

The exporter automatically detects CI environments and suppresses rich terminal formatting (colors, spinner animations, progress bar redraws) so that log output is clean and readable in CI logs.

Detection is based on two standard environment variables:

| Variable | Effect |
| -------- | ------ |
| `CI=true` | Disables ANSI color codes and live terminal output |
| `NO_COLOR=1` | Same effect (follows the [no-color.org](https://no-color.org) convention) |
| `DEBUG=true` | Enables verbose debug logging and additional diagnostics |

Most CI platforms (GitHub Actions, GitLab CI, CircleCI, Jenkins, etc.) set `CI=true` automatically.

You can also reduce output verbosity via the `export.log_level` config option (or by setting it to `WARNING` for quiet runs):

```sh
cme config  # set export.log_level to WARNING
```

This is useful for using different configs for different environments or for scripting.

## Update

Update python package via pip.

```sh
pip install confluence-markdown-exporter --upgrade
```

## Compatibility

This package is not tested extensively. Please check all output and report any issue [here](https://github.com/Spenhouet/confluence-markdown-exporter/issues).
It generally was tested on:

- Confluence Cloud 1000.0.0-b5426ab8524f (2025-05-28)
- Confluence Server 8.5.20

## Known Issues

1. **Missing Attachment File ID on Server**: For some Confluence Server version/configuration the attachment file ID might not be provided (https://github.com/Spenhouet/confluence-markdown-exporter/issues/39). In the default configuration, this is used for the export path. Solution: Adjust the attachment path in the export config and use the `{attachment_id}` or `{attachment_title}` instead.
2. **Connection Issues when behind Proxy or VPN**: There might be connection issues if your Confluence Server is behind a proxy or VPN (https://github.com/Spenhouet/confluence-markdown-exporter/issues/38). If you experience issues, help to fix this is appreciated.

## Contributing

If you would like to contribute, please read [our contribution guideline](CONTRIBUTING.md).

## License

This tool is an open source project released under the [MIT License](LICENSE).
