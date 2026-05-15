---
id: troubleshooting
title: Troubleshooting
sidebar_position: 6
---

# Troubleshooting

## Known issues and limitations

### Missing attachment file ID on Server

For some Confluence Server versions / configurations, the attachment file ID is not returned by the API ([#39](https://github.com/Spenhouet/confluence-markdown-exporter/issues/39)).

In that case, `{attachment_file_id}` automatically falls back to the content id, so the default [`export.attachment_path`](./configuration/options.md#exportattachment_path) template still produces unique filenames out of the box.

If you prefer human-readable filenames over numeric IDs, set `export.attachment_path` to use `{attachment_title}{attachment_extension}`, e.g.:

```sh
cme config set export.attachment_path='{space_name}/attachments/{attachment_title}{attachment_extension}'
```

### Connection issues behind proxy or VPN

There might be connection issues if your Confluence Server is behind a proxy or VPN ([#38](https://github.com/Spenhouet/confluence-markdown-exporter/issues/38)). If you experience issues, help to fix this is appreciated.

## Reporting bugs

Open an issue on the [GitHub issue tracker](https://github.com/Spenhouet/confluence-markdown-exporter/issues) and include:

1. Your Confluence flavour and version (Cloud, Server, Data Center)
2. The exact command you ran
3. The full output, ideally with `cme config set export.log_level=DEBUG` enabled
4. A minimal example page (if possible) reproducing the issue
