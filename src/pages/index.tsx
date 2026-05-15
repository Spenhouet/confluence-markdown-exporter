import React, { type ReactNode } from "react";
import clsx from "clsx";
import Link from "@docusaurus/Link";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import Layout from "@theme/Layout";
import CodeBlock from "@theme/CodeBlock";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import Admonition from "@theme/Admonition";
import HomepageFeatures from "@site/src/components/HomepageFeatures";
import styles from "./index.module.css";

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <header className={clsx("hero", styles.heroBanner)}>
      <div className="container">
        <img
          src="img/logo.png"
          alt={siteConfig.title}
          className="hero-logo"
        />
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link
            className="button button--hero button--lg"
            to="/installation"
          >
            Get started →
          </Link>
          <Link
            className="button button--hero-secondary button--lg"
            to="https://github.com/Spenhouet/confluence-markdown-exporter"
          >
            View on GitHub
          </Link>
        </div>
      </div>
    </header>
  );
}

const INSTALL_SNIPPETS = {
  linux: `# Installs an isolated, self-updating CLI via uv.
curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh`,
  macos: `# Installs an isolated, self-updating CLI via uv.
curl -LsSf uvx.sh/confluence-markdown-exporter/install.sh | sh`,
  windows: `powershell -ExecutionPolicy ByPass -c "irm https://uvx.sh/confluence-markdown-exporter/install.ps1 | iex"`,
  pip: `pip install confluence-markdown-exporter`,
  uv: `# Install as an isolated tool…
uv tool install confluence-markdown-exporter

# …or run it once without installing:
uvx confluence-markdown-exporter --help`,
  docker: `# Pull and run the prebuilt image (non-interactive / CI use).
docker pull spenhouet/confluence-markdown-exporter:latest
docker run --rm spenhouet/confluence-markdown-exporter --help`,
};

function InstallTabs() {
  return (
    <Tabs groupId="install-method" queryString>
      <TabItem value="linux" label="Linux">
        <CodeBlock language="bash">{INSTALL_SNIPPETS.linux}</CodeBlock>
      </TabItem>
      <TabItem value="macos" label="macOS">
        <CodeBlock language="bash">{INSTALL_SNIPPETS.macos}</CodeBlock>
      </TabItem>
      <TabItem value="windows" label="Windows">
        <CodeBlock language="powershell">{INSTALL_SNIPPETS.windows}</CodeBlock>
      </TabItem>
      <TabItem value="pip" label="pip">
        <CodeBlock language="bash">{INSTALL_SNIPPETS.pip}</CodeBlock>
      </TabItem>
      <TabItem value="uv" label="uv">
        <CodeBlock language="bash">{INSTALL_SNIPPETS.uv}</CodeBlock>
      </TabItem>
      <TabItem value="docker" label="Docker">
        <CodeBlock language="bash">{INSTALL_SNIPPETS.docker}</CodeBlock>
      </TabItem>
    </Tabs>
  );
}

function QuickstartSection() {
  return (
    <section className={styles.quickstart}>
      <div className="container">
        <div className="row">
          <div className="col col--8 col--offset-2">
            <h2 className={styles.quickstartTitle}>Get going in 60 seconds</h2>
            <p className={styles.quickstartLead}>
              Install, authenticate, export. That's the whole flow.
            </p>

            <h3 className={styles.stepTitle}>1. Install</h3>
            <InstallTabs />

            <Admonition type="info" title="Using the Docker image?">
              Steps 2 and 3 below use the local <code>cme</code> CLI. Inside the
              Docker image there is no interactive <code>cme config</code> menu;
              you supply a pre-defined config (mounted JSON file or
              <code> CME_*</code> env vars) and run a single export command
              per container invocation. See the{" "}
              <Link to="/docker">Docker page</Link> for the non-interactive
              flow.
            </Admonition>

            <h3 className={styles.stepTitle}>2. Authenticate</h3>
            <CodeBlock language="bash">
              {`cme config edit auth.confluence`}
            </CodeBlock>

            <h3 className={styles.stepTitle}>3. Export</h3>
            <CodeBlock language="bash">
              {`# A page, a subtree, an entire space, or every space of an org:
cme pages   https://example.atlassian.net/wiki/spaces/SPACE/pages/123/Title
cme spaces  https://example.atlassian.net/wiki/spaces/SPACE
cme orgs    https://example.atlassian.net`}
            </CodeBlock>

            <p className={styles.quickstartFooter}>
              Detailed instructions and per-target presets in the{" "}
              <Link to="/installation">installation docs</Link>.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout
      title={siteConfig.title}
      description={siteConfig.tagline}
    >
      <HomepageHeader />
      <main>
        <HomepageFeatures />
        <QuickstartSection />
      </main>
    </Layout>
  );
}
