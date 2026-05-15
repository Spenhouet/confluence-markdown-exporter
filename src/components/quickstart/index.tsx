import React, { type ReactNode } from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import CodeBlock from "@theme/CodeBlock";
import Link from "@docusaurus/Link";

/**
 * Build a six-tab group keyed by the install-method groupId, so it stays in
 * sync with the install tabs on landing / intro / installation pages.
 *
 * The five non-docker tabs share the same `local` content; the docker tab
 * shows the container equivalent.
 */
function makeStepTabs(local: ReactNode, docker: ReactNode) {
  return (
    <Tabs groupId="install-method" queryString>
      <TabItem value="linux" label="Linux">
        {local}
      </TabItem>
      <TabItem value="macos" label="macOS">
        {local}
      </TabItem>
      <TabItem value="windows" label="Windows">
        {local}
      </TabItem>
      <TabItem value="pip" label="pip">
        {local}
      </TabItem>
      <TabItem value="uv" label="uv">
        {local}
      </TabItem>
      <TabItem value="docker" label="Docker">
        {docker}
      </TabItem>
    </Tabs>
  );
}

/** Step 2: Authenticate. Interactive `cme config` locally, JSON config for Docker. */
export function AuthenticateTabs() {
  return makeStepTabs(
    <CodeBlock language="bash">{`cme config edit auth.confluence`}</CodeBlock>,
    <>
      <p>
        The container has no interactive menu. Generate the JSON config on a
        workstation first, then mount it (or pass credentials via{" "}
        <code>CME_AUTH__*</code> env vars):
      </p>
      <CodeBlock language="bash" title="On your workstation">
        {`# Writes ~/.config/confluence-markdown-exporter/app_data.json
cme config edit auth.confluence`}
      </CodeBlock>
      <p>
        Copy that <code>app_data.json</code> to your CI repo or secret store,
        then mount it on every container run (next step). See the{" "}
        <Link to="/docker">Docker page</Link> for the env-var alternative.
      </p>
    </>,
  );
}

/** Step 3: Export. `cme pages …` locally, `docker run … pages …` for Docker. */
export function ExportTabs() {
  return makeStepTabs(
    <CodeBlock language="bash">
      {`# A page, a subtree, an entire space, or every space of an org:
cme pages   https://example.atlassian.net/wiki/spaces/SPACE/pages/123/Title
cme spaces  https://example.atlassian.net/wiki/spaces/SPACE
cme orgs    https://example.atlassian.net`}
    </CodeBlock>,
    <CodeBlock language="bash">
      {`docker run --rm \\
  -v "$PWD/app_data.json:/data/config/app_data.json:ro" \\
  -v "$PWD/output:/data/output" \\
  spenhouet/confluence-markdown-exporter \\
  pages https://example.atlassian.net/wiki/spaces/SPACE/pages/123/Title`}
    </CodeBlock>,
  );
}

/** "Verify the install" tab variants for the installation page. */
export function VerifyTabs() {
  return makeStepTabs(
    <CodeBlock language="bash">{`cme --help`}</CodeBlock>,
    <CodeBlock language="bash">
      {`docker run --rm spenhouet/confluence-markdown-exporter --help`}
    </CodeBlock>,
  );
}
