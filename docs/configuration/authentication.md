---
id: authentication
title: Authentication
sidebar_position: 3
---

# Authentication

:::note
Auth credentials use URL-keyed nested dicts (e.g. `auth.confluence["https://company.atlassian.net"]`) and cannot be mapped to flat ENV var names. Use `cme config edit auth.confluence` or `cme config set` for auth configuration.
:::

The fastest way to set credentials is the interactive menu:

```sh
cme config edit auth.confluence
cme config edit auth.jira
```

## Confluence

### auth.confluence.url

Confluence instance URL.

- Default: `""`

### auth.confluence.username

Confluence username/email.

- Default: `""`

### auth.confluence.api_token

Confluence API token.

- Default: `""`

### auth.confluence.pat

Confluence Personal Access Token.

- Default: `""`

### auth.confluence.cloud_id

Atlassian Cloud ID for the Confluence instance. When set, API calls are routed through the Atlassian API gateway (`https://api.atlassian.com/ex/confluence/{cloud_id}`), which enables the use of [scoped API tokens](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

For Atlassian Cloud instances (`.atlassian.net`) this is fetched and stored **automatically** on first connection. You can also set it manually. See [How to retrieve your Atlassian Cloud ID](https://support.atlassian.com/jira/kb/retrieve-my-atlassian-sites-cloud-id/).

- Default: `""`

## Jira

### auth.jira.url

Jira instance URL.

- Default: `""`

### auth.jira.username

Jira username/email.

- Default: `""`

### auth.jira.api_token

Jira API token.

- Default: `""`

### auth.jira.pat

Jira Personal Access Token.

- Default: `""`

### auth.jira.cloud_id

Atlassian Cloud ID for the Jira instance. Works identically to `auth.confluence.cloud_id` above, routing API calls through `https://api.atlassian.com/ex/jira/{cloud_id}`.

For Atlassian Cloud instances this is fetched and stored **automatically** on first connection.

- Default: `""`

## Generating API tokens

API tokens that are associated with Atlassian Cloud accounts can be generated [in your 'Account Settings'](https://id.atlassian.com/manage-profile/security/api-tokens) (in Jira/Confluence: profile picture in upper-right corner → _Account Settings_ → _Security_ → _Create and Manage API tokens_).

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
