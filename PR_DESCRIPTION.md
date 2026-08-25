# Support for Clientside-Rendered Macros (Gliffy, DrawIO on Server/DC)

## Problem
On Confluence Server/Data Center, Gliffy and DrawIO diagrams render clientside (JavaScript) in `body.view`. This means:
- Attachments are downloaded correctly
- But diagrams are **invisible** in markdown exports (only HTML placeholders)
- DrawIO Cloud format works because it has HTML patterns, but Server/DC doesn't

## Solution
Parse `body.storage` XML to extract diagram metadata (structured-macros), then render diagrams as markdown image links.

## Changes

### New Components
- **`Page._clientside_macro_attachment_names()`** – Extracts gliffy/drawio diagram references from `body.storage`
- **`Converter.convert_gliffy()`** – Renders Gliffy diagrams as markdown image links
- **`Converter.convert_drawio()`** – Now has fallback to `body.storage` for Server/DC compatibility

### Refactored
- **`_attachments_for_export()`** – Simplified by using generic `_clientside_macro_attachment_names()` instead of DrawIO-specific workarounds

### Files
```
confluence_markdown_exporter/confluence.py: +223/-29 (187 net insertions)
tests/unit/test_clientside_macros_conversion.py: +324 (new tests)
```

## Testing
Mock-based unit tests in `tests/unit/test_clientside_macros_conversion.py`:
- Gliffy/DrawIO extraction from `body.storage`
- Cloud format (HTML patterns) vs Server/DC format (storage-based)
- Missing diagrams/attachments error handling
- Wiki-style and markdown-style link rendering

All tests use fixtures, no hardcoded credentials or URLs.

## Backwards Compatibility
- ✅ Existing DrawIO/attachment patterns still work
- ✅ No CLI or config changes
- ✅ Cloud exports unaffected
- ✅ Server/DC now includes previously-missing diagrams

## Notes
- This pattern is generic—can be extended to other clientside-rendered macros (Lucidchart, Miro, etc.)
- Assumes standard `{name}.png` preview naming convention
- Storage parsing errors are logged as debug, won't break exports
