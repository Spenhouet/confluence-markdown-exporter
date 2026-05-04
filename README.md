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

### 1. Installation or Update

Install or update confluence-markdown-exporter with a single command.

**macOS and Linux**
```bash
curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh
```

**Windows**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://uvx.sh/confluence-markdown-exporter/install.ps1 | iex"
```

Installing a specific version
```bash
curl -LsSf uvx.sh/confluence-markdown-exporter/4.1.1/install.sh | sh
```

### 2. Exporting

Run the exporter with the desired Confluence page URL or space URL. Execute the console application by typing `confluence-markdown-exporter` and one of the commands `pages`, `pages-with-descendants`, `spaces`, `orgs` or `config`. If a command is unclear, you can always add `--help` to get additional information.

All export commands accept one or more URLs as space-separated arguments. Each command also has a singular alias (`page`, `page-with-descendants`, `space`, `org`) that behaves identically.

#### 2.1. Export Page(s)

Export one or more Confluence pages by URL:

```sh
cme pages <page-url>
cme pages <page-url-1> <page-url-2> ...

# Singular alias (identical behaviour):
cme page <page-url>
```

Supported page URL formats:
- Confluence Cloud: <https://company.atlassian.net/wiki/spaces/SPACEKEY/pages/123456789/Page+Title>
- Confluence Cloud (API gateway): <https://api.atlassian.com/ex/confluence/CLOUDID/wiki/spaces/SPACEKEY/pages/123456789/Page+Title>
- Confluence Server (long): <https://wiki.company.com/display/SPACEKEY/Page+Title>
- Confluence Server (short): <https://wiki.company.com/SPACEKEY/Page+Title>
- Confluence Server (param): <https://wiki.company.com/pages/viewpage.action?pageId=123456789>

#### 2.2. Export Page(s) with Descendants

Export one or more Confluence pages and all their descendant pages by URL:

```sh
cme pages-with-descendants <page-url>
cme pages-with-descendants <page-url-1> <page-url-2> ...

# Singular alias (identical behaviour):
cme page-with-descendants <page-url>
```

#### 2.3. Export Space(s)

Export all Confluence pages of one or more spaces by URL:

```sh
cme spaces <space-url>
cme spaces <space-url-1> <space-url-2> ...

# Singular alias (identical behaviour):
cme space <space-url>
```

Supported space URL formats:
- Confluence Cloud: <https://company.atlassian.net/wiki/spaces/SPACEKEY>
- Confluence Cloud (API gateway): <https://api.atlassian.com/ex/confluence/CLOUDID/wiki/spaces/SPACEKEY>
- Confluence Server (long): <https://wiki.company.com/display/SPACEKEY>
- Confluence Server (short): <https://wiki.company.com/SPACEKEY>

#### 2.4. Export all Spaces of Organization(s)

Export all Confluence pages across all spaces of one or more organizations by URL:

```sh
cme orgs <base-url>
cme orgs <base-url-1> <base-url-2> ...

# Singular alias (identical behaviour):
cme org <base-url>
```

### 3. Output

The exported Markdown file(s) will be saved in the configured output directory (see `export.output_path`) e.g.:

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

### Config Commands

| Command | Description |
| ------- | ----------- |
| `cme config` | Open the interactive configuration menu |
| `cme config list` | Print the full configuration as YAML |
| `cme config get <key>` | Print the value of a single config key |
| `cme config set <key=value>...` | Set one or more config values |
| `cme config edit <key>` | Open the interactive editor for a specific key |
| `cme config path` | Print the path to the config file |
| `cme config reset` | Reset all configuration to defaults |

#### Interactive Menu

```sh
cme config
```

Opens a full interactive menu where you can:

- See all config options and their current values
- Select any option to change it (including authentication)
- Navigate into nested sections (e.g. `auth.confluence`)
- Reset all config to defaults

#### List Current Configuration

```sh
cme config list           # YAML (default)
cme config list -o json   # JSON
```

Prints the entire current configuration. Output format defaults to YAML; use `-o json` for JSON.

#### Get a Single Value

```sh
cme config get export.log_level
cme config get connection_config.max_workers
```

Prints the current value of the specified key. Nested sections are printed as YAML.

#### Set Values

```sh
cme config set export.log_level=DEBUG
cme config set export.output_path=/tmp/export
cme config set export.skip_unchanged=false
```

Sets one or more key=value pairs directly. Values are parsed as JSON where possible (so `true`, `false`, and numbers work as expected), falling back to a plain string.

> [!Note]
> For auth keys that contain a URL (e.g. `auth.confluence.https://...`), use `cme config edit auth.confluence` instead — the interactive editor handles URL-based keys correctly.

#### Edit a Specific Key Interactively

```sh
cme config edit auth.confluence
cme config edit export.log_level
```

Opens the interactive editor directly at the specified config section, skipping the top-level menu.

#### Show Config File Path

```sh
cme config path
```

Prints the absolute path to the configuration file. Useful when `CME_CONFIG_PATH` is set or when locating the file for backup/inspection.

#### Reset to Defaults

```sh
cme config reset
cme config reset --yes   # skip confirmation
```

Resets the entire configuration to factory defaults after confirmation.

### Configuration Options

All options can be set via the config file (using `cme config set`) or overridden for the current session via environment variables. ENV vars take precedence over stored config and are **not** persisted. ENV var names use the `CME_` prefix and `__` as the nested delimiter (matching the key in uppercase).

#### export.*

##### export.log_level

Controls output verbosity: `DEBUG` (every step), `INFO` (key milestones), `WARNING` (warnings/errors only), `ERROR` (errors only).

- Default: `INFO`
- ENV Var: `CME_EXPORT__LOG_LEVEL`

##### export.output_path

The directory where all exported files and folders will be written. Used as the base for relative and absolute links.

- Default: `./` (current working directory)
- ENV Var: `CME_EXPORT__OUTPUT_PATH`

##### export.page_href

How to generate links to pages in Markdown. Options: `relative` (default), `absolute`, or `wiki`.

- Default: `relative`
- ENV Var: `CME_EXPORT__PAGE_HREF`

| Value | Output |
|-------|--------|
| `relative` | `[Page Title](../path/to/page.md)` |
| `absolute` | `[Page Title](/space/path/to/page.md)` |
| `wiki` | `[[Page Title]]` |

##### export.page_path

Path template for exported pages.

- Default: `{space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md`
- ENV Var: `CME_EXPORT__PAGE_PATH`

##### export.attachment_href

How to generate links to attachments in Markdown. Options: `relative` (default), `absolute`, or `wiki`.

- Default: `relative`
- ENV Var: `CME_EXPORT__ATTACHMENT_HREF`

| Value | Output |
|-------|--------|
| `relative` | `[file.pdf](../path/to/file.pdf)` / `![alt](../path/to/image.png)` |
| `absolute` | `[file.pdf](/space/attachments/file.pdf)` / `![alt](/space/attachments/image.png)` |
| `wiki` | `[[file.pdf\|File Title]]` / `![[image.png\|alt text]]` |

##### export.attachment_path

Path template for attachments.

- Default: `{space_name}/attachments/{attachment_file_id}{attachment_extension}`
- ENV Var: `CME_EXPORT__ATTACHMENT_PATH`

##### export.attachment_export_all

Export all attachments, not only those referenced by a page. Note: exporting large or many attachments increases export time.

- Default: `False`
- ENV Var: `CME_EXPORT__ATTACHMENT_EXPORT_ALL`

##### export.page_breadcrumbs

Whether to include breadcrumb links at the top of the page.

- Default: `True`
- ENV Var: `CME_EXPORT__PAGE_BREADCRUMBS`

##### export.page_properties_as_front_matter

Whether to convert Confluence Page Properties macro tables into YAML front matter. When enabled, key-value pairs in the macro are extracted and written as YAML front matter at the top of the exported file. When disabled, the macro is converted to a regular markdown table.

- Default: `True`
- ENV Var: `CME_EXPORT__PAGE_PROPERTIES_AS_FRONT_MATTER`

##### export.filename_encoding

Character mapping for filename encoding.

- Default: Default mappings for forbidden characters.
- ENV Var: `CME_EXPORT__FILENAME_ENCODING`

##### export.filename_length

Maximum length of filenames.

- Default: `255`
- ENV Var: `CME_EXPORT__FILENAME_LENGTH`

##### export.include_document_title

Whether to include the document title in the exported markdown file.

- Default: `True`
- ENV Var: `CME_EXPORT__INCLUDE_DOCUMENT_TITLE`

##### export.include_toc

Whether to export the Confluence Table of Contents macro. When enabled, the TOC is converted to markdown. When disabled, the TOC macro is removed from the output.

- Default: `True`
- ENV Var: `CME_EXPORT__INCLUDE_TOC`

##### export.enable_jira_enrichment

Fetch Jira issue data to enrich Confluence pages. When enabled, Jira issue links include the issue summary. Requires Jira auth to be configured.

- Default: `True`
- ENV Var: `CME_EXPORT__ENABLE_JIRA_ENRICHMENT`

##### export.inline_comments

Fetch and export open inline comments as a sidecar `.comments.md` file placed next to the exported page file, using the same path stem. Only open (non-resolved, non-dangling) comments are included. Each comment thread shows the annotated text as a blockquote, followed by the author, date, and comment body. Replies are listed flat below the parent comment. Disabled by default — adds one extra API call per comment thread per page.

- Default: `False`
- ENV Var: `CME_EXPORT__INLINE_COMMENTS`

##### export.skip_unchanged

Skip exporting pages that have not changed since last export. Uses a lockfile to track page versions.

- Default: `True`
- ENV Var: `CME_EXPORT__SKIP_UNCHANGED`

##### export.cleanup_stale

After export, delete local files for pages removed from Confluence or whose export path has changed.

- Default: `True`
- ENV Var: `CME_EXPORT__CLEANUP_STALE`

##### export.lockfile_name

Name of the lock file used to track exported pages.

- Default: `confluence-lock.json`
- ENV Var: `CME_EXPORT__LOCKFILE_NAME`

##### export.existence_check_batch_size

Number of page IDs per batch when checking page existence during cleanup. Capped at 25 for self-hosted (CQL).

- Default: `250`
- ENV Var: `CME_EXPORT__EXISTENCE_CHECK_BATCH_SIZE`

#### connection_config.*

##### connection_config.backoff_and_retry

Enable automatic retry with exponential backoff.

- Default: `True`
- ENV Var: `CME_CONNECTION_CONFIG__BACKOFF_AND_RETRY`

##### connection_config.backoff_factor

Multiplier for exponential backoff.

- Default: `2`
- ENV Var: `CME_CONNECTION_CONFIG__BACKOFF_FACTOR`

##### connection_config.max_backoff_seconds

Maximum seconds to wait between retries.

- Default: `60`
- ENV Var: `CME_CONNECTION_CONFIG__MAX_BACKOFF_SECONDS`

##### connection_config.max_backoff_retries

Maximum number of retry attempts.

- Default: `5`
- ENV Var: `CME_CONNECTION_CONFIG__MAX_BACKOFF_RETRIES`

##### connection_config.retry_status_codes

HTTP status codes that trigger a retry.

- Default: `[413, 429, 502, 503, 504]`
- ENV Var: `CME_CONNECTION_CONFIG__RETRY_STATUS_CODES`

##### connection_config.timeout

Timeout in seconds for API requests. Prevents hanging on slow or unresponsive servers.

- Default: `30`
- ENV Var: `CME_CONNECTION_CONFIG__TIMEOUT`

##### connection_config.verify_ssl

Whether to verify SSL certificates for HTTPS requests.

- Default: `True`
- ENV Var: `CME_CONNECTION_CONFIG__VERIFY_SSL`

##### connection_config.use_v2_api

Enable Confluence REST API v2 endpoints. Supported on Atlassian Cloud and Data Center 8+. Disable for self-hosted Server instances.

- Default: `False`
- ENV Var: `CME_CONNECTION_CONFIG__USE_V2_API`

##### connection_config.max_workers

Maximum number of parallel workers for page export. Set to `1` for serial/debug mode. Higher values improve performance but may hit API rate limits.

- Default: `20`
- ENV Var: `CME_CONNECTION_CONFIG__MAX_WORKERS`

#### auth.*

> [!Note]
> Auth credentials use URL-keyed nested dicts (e.g. `auth.confluence["https://company.atlassian.net"]`) and cannot be mapped to flat ENV var names. Use `cme config edit auth.confluence` or `cme config set` for auth configuration.

##### auth.confluence.url

Confluence instance URL.

- Default: `""`

##### auth.confluence.username

Confluence username/email.

- Default: `""`

##### auth.confluence.api_token

Confluence API token.

- Default: `""`

##### auth.confluence.pat

Confluence Personal Access Token.

- Default: `""`

##### auth.confluence.cloud_id

Atlassian Cloud ID for the Confluence instance. When set, API calls are routed through the Atlassian API gateway (`https://api.atlassian.com/ex/confluence/{cloud_id}`), which enables the use of [scoped API tokens](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

For Atlassian Cloud instances (`.atlassian.net`) this is fetched and stored **automatically** on first connection. You can also set it manually — see [How to retrieve your Atlassian Cloud ID](https://support.atlassian.com/jira/kb/retrieve-my-atlassian-sites-cloud-id/).

- Default: `""`

##### auth.jira.url

Jira instance URL.

- Default: `""`

##### auth.jira.username

Jira username/email.

- Default: `""`

##### auth.jira.api_token

Jira API token.

- Default: `""`

##### auth.jira.pat

Jira Personal Access Token.

- Default: `""`

##### auth.jira.cloud_id

Atlassian Cloud ID for the Jira instance. Works identically to `auth.confluence.cloud_id` above, routing API calls through `https://api.atlassian.com/ex/jira/{cloud_id}`.

For Atlassian Cloud instances this is fetched and stored **automatically** on first connection.

- Default: `""`

You can always view and change the current config with the interactive menu above.

#### Generating API tokens

API tokens that are associated with Atlassian Cloud accounts can be generated [in your 'Account Settings'](https://id.atlassian.com/manage-profile/security/api-tokens) (in Jira/Confluence: profile picture in upper-right corner > _Account Settings_ > _Security_ > _Create and Manage API tokens_).
Scoped API tokens **require 'classic' scopes**; these scopes have been tested (giving full read-only access):

```text
read:confluence-content.all
read:account
read:confluence-content.permission
read:confluence-content.summary
read:confluence-groups
read:confluence-props
read:confluence-space.summary
read:confluence-user
read:me
readonly:content.attachment:confluence
search:confluence
```

### Configuration for Target Systems

Some platforms have specific requirements for Markdown formatting, file structure, or metadata. You can adjust the export configuration to optimize output for your target system. Below are some common examples:

#### Obsidian

Run the following command to configure the exporter for Obsidian:

```sh
cme config set \
  export.include_document_title=false \
  export.page_breadcrumbs=false \
  export.page_href=wiki \
  export.attachment_href=wiki
```

Obsidian natively renders the document title and page breadcrumbs, so both are disabled to avoid redundant output. Wiki-style links (`[[Page Title]]` and `![[attachment.png]]`) are used so Obsidian can resolve links by title across the vault without depending on the file system path.

> **Note:** Wiki links resolve by page title. If multiple pages share the same title across spaces, Obsidian may link to the wrong file. In that case, omit `export.page_href=wiki` and use `relative` or `absolute` links instead.

#### Azure DevOps (ADO) Wikis

Run the following command to configure the exporter for ADO Wikis:

```sh
cme config set \
  export.attachment_href=absolute \
  'export.attachment_path=.attachments/{attachment_file_id}{attachment_extension}' \
  'export.filename_encoding={" ":"-","\"":"%22","*":"%2A","-":"%2D",":":"%3A","<":"%3C",">":"%3E","?":"%3F","|":"%7C","\\":"_","#":"_","/":"_","\u0000":"_"}' \
  export.filename_length=200
```

ADO Wikis require absolute attachment links and expect attachments in a specific `.attachments/` folder. Filenames are sanitized to match ADO's restrictions: spaces become dashes, dashes are percent-encoded, and other forbidden characters are replaced with underscores. The filename length is capped to stay within ADO's limits.

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

Most CI platforms (GitHub Actions, GitLab CI, CircleCI, Jenkins, etc.) set `CI=true` automatically.

You can control output verbosity via the `CME_EXPORT__LOG_LEVEL` env var or the `export.log_level` config option:

```sh
# Enable verbose debug logging for a single run (not persisted):
CME_EXPORT__LOG_LEVEL=DEBUG cme pages <page-url>

# Reduce verbosity permanently:
cme config set export.log_level=WARNING

# Or for the current session only:
CME_EXPORT__LOG_LEVEL=WARNING cme pages <page-url>
```

This is useful for using different log levels for different environments or for scripting.


## Compatibility

This package is not tested extensively. Please check all output and report any issue [here](https://github.com/Spenhouet/confluence-markdown-exporter/issues).
It generally was tested on:

- Confluence Cloud 1000.0.0-b5426ab8524f (2025-05-28)
- Confluence Server 8.5.20

## Known Issues and Limitations

1. **Missing Attachment File ID on Server**: For some Confluence Server version/configuration the attachment file ID might not be provided (https://github.com/Spenhouet/confluence-markdown-exporter/issues/39). In the default configuration, this is used for the export path. Solution: Adjust the attachment path in the export config and use the `{attachment_id}` or `{attachment_title}{attachment_extension}` instead.
2. **Connection Issues when behind Proxy or VPN**: There might be connection issues if your Confluence Server is behind a proxy or VPN (https://github.com/Spenhouet/confluence-markdown-exporter/issues/38). If you experience issues, help to fix this is appreciated.

## Contributing

If you would like to contribute, please read [our contribution guideline](CONTRIBUTING.md).

## License

This tool is an open source project released under the [MIT License](LICENSE).
