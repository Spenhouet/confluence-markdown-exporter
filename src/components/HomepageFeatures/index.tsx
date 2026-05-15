import React, { type ReactNode } from "react";
import clsx from "clsx";
import Link from "@docusaurus/Link";
import styles from "./styles.module.css";

type Feature = {
  icon: string;
  title: string;
  description: ReactNode;
  href: string;
};

const FEATURES: Feature[] = [
  {
    icon: "🚀",
    title: "One-command install",
    href: "/installation",
    description: (
      <>
        A single curl/PowerShell line installs an isolated, self-updating CLI
        via <code>uv</code>. No virtualenv juggling.
      </>
    ),
  },
  {
    icon: "📚",
    title: "Pages, spaces, orgs",
    href: "/usage",
    description: (
      <>
        Export a single page, a page subtree, an entire space, or every space
        in your Atlassian organisation.
      </>
    ),
  },
  {
    icon: "⚡",
    title: "Incremental by default",
    href: "/features",
    description: (
      <>
        Skips unchanged pages using a lockfile. Re-runs export only what
        actually moved since last time.
      </>
    ),
  },
  {
    icon: "🎯",
    title: "Target presets",
    href: "/configuration/target-systems",
    description: (
      <>
        Pre-baked configurations for Obsidian (wiki links, Dataview, Meta Bind)
        and Azure DevOps wikis (sanitized filenames, attachments folder).
      </>
    ),
  },
  {
    icon: "🧩",
    title: "Macros & add-ons",
    href: "/features",
    description: (
      <>
        Status badges, panels, page properties, draw.io, PlantUML, Mermaid,
        include/excerpt: all converted to portable Markdown.
      </>
    ),
  },
  {
    icon: "🔐",
    title: "Cloud & Server",
    href: "/configuration/authentication",
    description: (
      <>
        Works against Confluence Cloud, the Atlassian API gateway, and
        on-premise Server / Data Center. API tokens, PATs, scoped tokens: all
        supported.
      </>
    ),
  },
];

function FeatureCard({ icon, title, description, href }: Feature) {
  return (
    <Link to={href} className={clsx("col col--4", styles.featureCol)}>
      <div className={clsx("feature-card", styles.featureCard)}>
        <span className="feature-icon" aria-hidden="true">
          {icon}
        </span>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </Link>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FEATURES.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </div>
      </div>
    </section>
  );
}
