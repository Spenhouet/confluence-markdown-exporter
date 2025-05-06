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

### 3. Exporting

Run the exporter with the desired Confluence page ID or space key.

Export a single Confluence page:

```sh
confluence-markdown-exporter page <page-id e.g. 645208921> <output path e.g. ./output_path/>
```

Export a Confluence page and all it's descendants:

```sh
confluence-markdown-exporter page-with-descendants <page-id e.g. 645208921> <output path e.g. ./output_path/>
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

## Configuration Options

By default the converter uses a GitHub Flavored Markdown (GFM). You can also choose an Obsidian flavored markdown by setting:

```sh
export MARKDOWN_STYLE="Obsidian"
```

Via `PAGE_PATH` and `ATTACHMENT_PATH` you can customize how pages and attachments are organized in the output directory. 

By default, pages are stored at:
```sh
export PAGE_PATH="{space_name}/{homepage_title}/{ancestor_titles}/{page_title}.md"
```
Available variables:
  - `{space_key}`: The key of the Confluence space.
  - `{space_name}`: The name of the Confluence space.
  - `{homepage_id}`: The ID of the homepage of the Confluence space.
  - `{homepage_title}`: The title of the homepage of the Confluence space.
  - `{ancestor_ids}`: A slash-separated list of ancestor page IDs.
  - `{ancestor_titles}`: A slash-separated list of ancestor page titles.
  - `{page_id}`: The unique ID of the Confluence page.
  - `{page_title}`: The title of the Confluence page.

By default, pages are stored at:
```sh
export ATTACHMENT_PATH="{space_name}/attachments/{attachment_file_id}{attachment_extension}"
```
Available variables:
  - `{space_key}`: The key of the Confluence space.
  - `{space_name}`: The name of the Confluence space.
  - `{homepage_id}`: The ID of the homepage of the Confluence space.
  - `{homepage_title}`: The title of the homepage of the Confluence space.
  - `{ancestor_ids}`: A slash-separated list of ancestor page IDs.
  - `{ancestor_titles}`: A slash-separated list of ancestor page titles.
  - `{attachment_id}`: The unique ID of the attachment.
  - `{attachment_title}`: The title of the attachment.
  - `{attachment_file_id}`: The file ID of the attachment.
  - `{attachment_extension}`: The file extension of the attachment, including the leading dot.

## Contributing

If you would like to contribute, please read [our contribution guideline](CONTRIBUTING.md).

## License

This tool is an open source project released under the [MIT License](LICENSE).
