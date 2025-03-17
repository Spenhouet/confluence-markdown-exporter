# confluence-markdown-exporter

The confluence-markdown-exporter is a tool designed to convert Confluence pages into Markdown format. This exporter helps in migrating content from Confluence to platforms that support Markdown, ensuring that the content retains its structure and formatting.

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

1. **Installation**: Clone the repository and install the necessary dependencies.

   ```sh
   git clone https://github.com/yourusername/confluence-markdown-exporter.git
   cd confluence-markdown-exporter
   pip install -r requirements.txt
   ```

2. **Configuration**: Configure the exporter by copying the `.env.template` file to `.env` and filling in your Confluence instance details and authentication.

   ```sh
   cp .env.template .env
   ```

   Edit the `.env` file to include your Confluence details:

   ```env
   USERNAME=your-username
   PASSWORD=your-api-token
   URL=https://your-confluence-instance.atlassian.net
   ```

3. **Exporting**: Run the exporter with the desired Confluence page ID.

   ```sh
   python confluence_markdown_exporter/main.py page 123456 ./output_path/
   ```

4. **Output**: The exported Markdown file will be saved in the `output` directory.
   ```sh
   output_path/
   └── space-abcdef
        └── page-123456.md
   ```

## Contributing

If you would like to contribute, please read [our contribution guideline](CONTRIBUTING.md).

## License

This tool is an open source project released under the [MIT License](LICENSE).
