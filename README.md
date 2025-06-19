<p align="center">
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter"><img src="https://raw.githubusercontent.com/Spenhouet/confluence-markdown-exporter/b8caaba935eea7e7017b887c86a740cb7bf99708/logo.png" alt="confluence-markdown-exporter"></a>
</p>
<p align="center">
    <em>The confluence-markdown-exporter exports Confluence pages in Markdown format. This exporter helps in migrating content from Confluence to platforms that support Markdown e.g. Obsidian, Gollum, Azure DevOps, Foam, Dendron and more.</em>
</p>
<p align="center">
  <a href="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/publish.yml"><img src="https://github.com/Spenhouet/confluence-markdown-exporter/actions/workflows/publish.yml/badge.svg" alt="Build and publish to PyPI"></a>
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

## Usage

To use the confluence-markdown-exporter, follow these steps:

### 1. Installation

Install python package via pip.

```sh
pip install confluence-markdown-exporter
```

### 2. Configure Authentication

You must set environment variables for **one** of the following authentication options:

1. Username + API Token

   - `ATLASSIAN_USERNAME`: Your Atlassian account email address
   - `ATLASSIAN_API_TOKEN`: An API token created at  
      https://id.atlassian.com/manage-profile/security/api-tokens

2. Personal Access Token (PAT)

   - `ATLASSIAN_PAT`: A Personal Access Token (used instead of username+token)

In all cases, you must also set:

- `ATLASSIAN_URL`: Your Atlassian instance URL (e.g. `https://company.atlassian.net`)

Here an example setting the environment variables for the Username + API Token authentication for the current terminal session.

```sh
export ATLASSIAN_USERNAME="work mail address"
export ATLASSIAN_API_TOKEN="API token Test"
export ATLASSIAN_URL="https://company.atlassian.net"
```

If you have separate Confluence and Jira instances or authentication, you can provide them via `CONFLUENCE_` or `JIRA_` prefixed environment variables.

### 3. Exporting

Run the exporter with the desired Confluence page ID or space key.

Export a single Confluence page by ID or URL:

```sh
confluence-markdown-exporter page <page-id e.g. 645208921 or page-url e.g. https://company.atlassian.net/MySpace/My+Page+Title> <output path e.g. ./output_path/>
```

Export a Confluence page and all it's descendants:

```sh
confluence-markdown-exporter page-with-descendants <page-id e.g. 645208921 or page-url e.g. https://company.atlassian.net/MySpace/My+Page+Title> <output path e.g. ./output_path/>
```

Export all Confluence pages of a single Space:

```sh
confluence-markdown-exporter space <space-key e.g. MYSPACE> <output path e.g. ./output_path/>
```

Export all Confluence pages across all spaces:

```sh
confluence-markdown-exporter all-spaces <output path e.g. ./output_path/>
```

> [!TIP]
> Instead of `confluence-markdown-exporter` you can also use the shorthand `cf-export`.

### 4. Output

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
confluence-markdown-exporter config
```

This will open a menu where you can:
- See all config options and their current values
- Select a config to change (including authentication)
- Reset all config to defaults
- Navigate directly to any config section (e.g. `auth.confluence`)

### Available configuration keys

| Key | Description | Default |
|-----|-------------|---------|
| output_directory | Output directory for markdown exports | ~/confluence_exports |
| markdown_style | Markdown style: GFM or Obsidian | GFM |
| page_path | Path template for exported pages | {space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md |
| attachment_path | Path template for attachments | {space_name}/attachments/{attachment_file_id}{attachment_extension} |
| include_attachments | Whether to include attachments in export | True |
| retry_config.backoff_and_retry | Enable automatic retry with exponential backoff | True |
| retry_config.backoff_factor | Multiplier for exponential backoff | 2 |
| retry_config.max_backoff_seconds | Maximum seconds to wait between retries | 60 |
| retry_config.max_backoff_retries | Maximum number of retry attempts | 5 |
| retry_config.retry_status_codes | HTTP status codes that trigger a retry | \[413, 429, 502, 503, 504\] |
| auth.confluence.url | Confluence instance URL | "" |
| auth.confluence.username | Confluence username/email | "" |
| auth.confluence.api_token | Confluence API token | "" |
| auth.confluence.pat | Confluence Personal Access Token | "" |
| auth.jira.url | Jira instance URL | "" |
| auth.jira.username | Jira username/email | "" |
| auth.jira.api_token | Jira API token | "" |
| auth.jira.pat | Jira Personal Access Token | "" |

You can always view and change the current config with the interactive menu above.

## Compatibility

This package is not tested extensively. Please check all output and report any issue [here](https://github.com/Spenhouet/confluence-markdown-exporter/issues).
It generally was tested on:
- Confluence Cloud 1000.0.0-b5426ab8524f (2025-05-28)
- Confluence Server 8.5.20

## Contributing

If you would like to contribute, please read [our contribution guideline](CONTRIBUTING.md).

## License

This tool is an open source project released under the [MIT License](LICENSE).
