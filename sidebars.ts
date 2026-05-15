import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebars: SidebarsConfig = {
  docsSidebar: [
    "intro",
    {
      type: "category",
      label: "Quickstart",
      collapsed: false,
      items: ["installation", "usage"],
    },
    "features",
    {
      type: "category",
      label: "Configuration",
      collapsed: false,
      link: { type: "doc", id: "configuration/index" },
      items: [
        "configuration/options",
        "configuration/authentication",
        "configuration/target-systems",
        "configuration/ci",
      ],
    },
    "compatibility",
    "troubleshooting",
    "contributing",
  ],
};

export default sidebars;
