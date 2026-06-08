// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'RustChain',
  tagline: 'Proof-of-Antiquity blockchain — 1 CPU = 1 vote, vintage hardware wins',
  favicon: 'img/favicon.ico',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Production URL. GitHub Pages project site for Scottcjn/Rustchain.
  // Change url+baseUrl here if a custom domain is added later.
  url: 'https://scottcjn.github.io',
  baseUrl: '/Rustchain/',

  // GitHub pages deployment config.
  organizationName: 'Scottcjn', // GitHub org/user name.
  projectName: 'Rustchain', // Repo name.

  // Importing 151 GitHub-authored docs: do NOT fail the build on cross-doc
  // links that don't resolve to Docusaurus routes. Warnings give us a
  // punch-list to fix incrementally instead of a hard stop.
  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  // Parse .md as CommonMark (not MDX) so GitHub-style `<...>` and `{...}`
  // literals don't get compiled as JSX/JS. .mdx files still use MDX.
  markdown: {
    format: 'detect',
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          // Use the repo's existing docs/ folder (sibling of website/).
          path: '../docs',
          routeBasePath: 'docs',
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/Scottcjn/Rustchain/tree/main/docs/',
        },
        // No blog for the protocol docs site (phase 1).
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/docusaurus-social-card.jpg',
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'RustChain',
        logo: {
          alt: 'RustChain Logo',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://github.com/Scottcjn/Rustchain',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {
                label: 'Documentation',
                to: '/docs',
              },
            ],
          },
          {
            title: 'Project',
            items: [
              {
                label: 'GitHub',
                href: 'https://github.com/Scottcjn/Rustchain',
              },
              {
                label: 'Bounties',
                href: 'https://github.com/Scottcjn/rustchain-bounties',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Elyan Labs · RustChain. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
