# GitHub Badges & README UI Cheat Sheet

> **Reviewed:** 19 July 2026<br>
> **Scope:** GitHub repository and profile READMEs, native workflow badges, Shields.io badges, linked badge-buttons, external cards, and GitHub-safe layout elements.

Badges are normally remotely hosted SVG images embedded with ordinary Markdown image syntax. A badge becomes button-like when the image is wrapped in a link; it is still an image and link rather than a native interactive control.

This guide uses three kinds of examples:

1. **Raw source** — literal Markdown or HTML to copy.
2. **Rendered example** — a fixed placeholder that does not track a live repository.
3. **Expected on GitHub** — used when a template requires real repository, workflow, package, or account details.

> Replace `OWNER`, `REPOSITORY`, `WORKFLOW_FILE`, `BRANCH`, `PACKAGE`, and other uppercase placeholders before using a dynamic template.

## Companion reference

For ordinary Markdown, GFM, tables, images, permitted HTML, `<details>`, theme-aware `<picture>` blocks, and other formatting, see the [Markdown & GitHub Flavored Markdown Cheat Sheet](md-and-gh-cheat-sheet.md).

---

## Table of contents

- [1. Main badge and widget resources](#1-main-badge-and-widget-resources)
- [2. Badge anatomy](#2-badge-anatomy)
- [3. Fixed placeholder badges](#3-fixed-placeholder-badges)
- [4. Native GitHub Actions status badges](#4-native-github-actions-status-badges)
- [5. Shields.io GitHub repository badges](#5-shieldsio-github-repository-badges)
- [6. Package and registry badges](#6-package-and-registry-badges)
- [7. Customising Shields.io badges](#7-customising-shieldsio-badges)
- [8. Clickable badges and download buttons](#8-clickable-badges-and-download-buttons)
- [9. Badge rows and alignment](#9-badge-rows-and-alignment)
- [10. Dynamic JSON and endpoint badges](#10-dynamic-json-and-endpoint-badges)
- [11. Coverage and security badges](#11-coverage-and-security-badges)
- [12. Profile cards, icons, and decorative widgets](#12-profile-cards-icons-and-decorative-widgets)
- [13. GitHub-safe README UI elements](#13-github-safe-readme-ui-elements)
- [14. Limitations, accessibility, and maintenance](#14-limitations-accessibility-and-maintenance)
- [15. Compact templates](#15-compact-templates)
- [16. Sources](#16-sources)

---

## 1. Main badge and widget resources

| Resource | Hosted by | Main use | Notes |
|---|---|---|---|
| [GitHub Actions workflow badges](https://docs.github.com/actions/managing-workflow-runs/adding-a-workflow-status-badge) | GitHub | Native passing/failing workflow status | Best source for a repository's own Actions workflow status. |
| [GitHub Sponsor button](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository) | GitHub | Native repository-header funding menu | Configured with `.github/FUNDING.yml`; it is repository chrome, not README markup. |
| [Shields.io](https://shields.io/) | Shields.io | Static and dynamic badges for GitHub, package registries, coverage services, downloads, licences, and custom data | Includes an interactive badge builder and per-badge documentation. |
| [Shields.io static badges](https://shields.io/badges/static-badge) | Shields.io | Fixed placeholder or manually maintained values | Used for the rendered examples in this guide so values do not change. |
| [Shields.io dynamic JSON badges](https://shields.io/badges/dynamic-json-badge) | Shields.io | Extracting a value from a public JSON document | Requires a public URL and a JSONPath query. |
| [Shields.io endpoint badges](https://shields.io/badges/endpoint-badge) | Shields.io | Rendering data returned by a badge-compatible JSON endpoint | Useful for fully custom metrics. |
| [Simple Icons](https://simpleicons.org/) | Simple Icons | Brand-logo names and SVG icons | Shields.io uses Simple Icons slugs for many `logo=` values. Check the project's legal disclaimer before using a brand mark. |
| [Codecov status badges](https://docs.codecov.com/docs/status-badges) | Codecov | Test-coverage and bundle-size status | Requires a configured Codecov repository; private badges may require a token. |
| [Coveralls](https://docs.coveralls.io/) | Coveralls | Test-coverage status | Use the badge generated for the configured repository. |
| [OpenSSF Scorecard](https://github.com/ossf/scorecard#scorecard-badges) | OpenSSF | Open-source security-health score | The repository must publish Scorecard results before the badge is available. |
| [GitHub Readme Stats](https://github.com/anuraghazra/github-readme-stats) | Community project | Profile statistics, language, repository, gist, and WakaTime cards | Third-party dynamic service; self-hosting is recommended when reliability matters. |
| [Skill Icons](https://skillicons.dev/) ([source](https://github.com/tandpfun/skill-icons)) | Community project | Technology and skill icon rows | Fixed icon selection; not a GitHub statistic. |
| [Readme Typing SVG](https://readme-typing-svg.demolab.com/) ([source](https://github.com/DenverCoder1/readme-typing-svg)) | Community project | Animated fixed text rendered as SVG | Decorative; provide useful surrounding text for accessibility. |
| [GitHub Readme Streak Stats](https://github-readme-streak-stats.herokuapp.com/) ([source](https://github.com/DenverCoder1/github-readme-streak-stats)) | Community project | Contribution-streak cards | Third-party and account-dependent. |
| [GitHub Profile Trophy](https://github.com/ryo-ma/github-profile-trophy) | Community project | Profile achievement cards | Third-party and account-dependent. |
| [Badgen](https://badgen.net/) | Community service | Alternative static and live badge generator | Useful when a Shields.io-specific integration is not required. |
| [For the Badge](https://forthebadge.com/) | Community service | Large decorative SVG/PNG badges | Better for visual labels than authoritative live status. |
| [readme.so](https://readme.so/) | Community editor | Building an ordinary repository README section by section | Export and review the Markdown before committing it. |
| [GitHub Profile README Generator](https://rahuldkjain.github.io/gh-profile-readme-generator/) ([source](https://github.com/rahuldkjain/github-profile-readme-generator)) | Community generator | Profile README structure, icons, social links, and optional cards | Generated third-party widgets inherit their providers' limitations. |
| [Devicon](https://devicon.dev/) ([source](https://github.com/devicons/devicon)) | Community icon library | Development-language and tool SVGs | Use direct SVG images in GitHub Markdown; icon-font HTML requires CSS and is unsuitable for a README. |
| [Read the Docs badges](https://docs.readthedocs.com/platform/stable/badges.html) | Read the Docs | Documentation build status | Use when the project is actually built on Read the Docs. |
| [Crowdin](https://crowdin.com/) | Crowdin | Translation-project destination and branding | A translation badge or button should link to the real Crowdin project. |
| [Ko-fi](https://ko-fi.com/), [Patreon](https://www.patreon.com/), and [PayPal](https://www.paypal.com/) | Respective service | Support or donation destinations | Use service-provided assets or a clearly labelled static badge; never imply an endorsement. |
| [Carbon](https://carbon.now.sh/) | Community tool | Exporting styled source-code screenshots | Keep copyable code in a real code block as well. |

### 1.1 First-time decision guide

| What you want to show | Start here | Recommended approach |
|---|---|---|
| Whether a GitHub Actions build passes | [GitHub workflow badges](https://docs.github.com/actions/managing-workflow-runs/adding-a-workflow-status-badge) | Use GitHub's native workflow badge. |
| Release, downloads, licence, stars, issues, or repository activity | [Shields.io GitHub badges](https://shields.io/badges) | Select the matching GitHub badge and replace the repository placeholders. |
| A fixed label such as supported OS or documentation link | [Shields.io static badge builder](https://shields.io/badges/static-badge) | Create a static badge, then wrap it in a useful link when appropriate. |
| Package version or registry downloads | [Shields.io badge catalogue](https://shields.io/badges) | Use the badge for npm, PyPI, Docker Hub, crates.io, NuGet, RubyGems, or the relevant registry. |
| Test coverage | [Codecov](https://docs.codecov.com/docs/status-badges), [Coveralls](https://docs.coveralls.io/app-ui), or the project's coverage provider | Generate the badge from the configured project dashboard. |
| Documentation build status | [Read the Docs badges](https://docs.readthedocs.com/platform/stable/badges.html) | Copy the badge for the real Read the Docs project. |
| Security-health summary | [OpenSSF Scorecard](https://github.com/ossf/scorecard#scorecard-badges) | Publish Scorecard results, then use its official badge. |
| Technology or brand icons | [Skill Icons](https://skillicons.dev/), [Simple Icons](https://simpleicons.org/), or [Devicon](https://devicon.dev/) | Use a fixed icon list or direct SVG image. Check brand guidance. |
| A visually large decorative badge | [For the Badge](https://forthebadge.com/) | Export SVG/PNG or copy the generated Markdown. Do not present it as live verification. |
| A native funding menu beside the repository controls | [GitHub Sponsor button](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository) | Configure `.github/FUNDING.yml` on the default branch; this is outside the README itself. |
| A complete repository README | [readme.so](https://readme.so/) | Assemble the sections, export the Markdown, and verify every generated link. |
| A profile README | [GitHub Profile README Generator](https://rahuldkjain.github.io/gh-profile-readme-generator/) | Generate a starting point, then remove unnecessary counters and third-party widgets. |
| Styled code image | [Carbon](https://carbon.now.sh/) | Export an image, but retain accessible copyable code nearby. |
| Fully custom public data | [Shields.io dynamic JSON](https://shields.io/badges/dynamic-json-badge) or [endpoint badges](https://shields.io/badges/endpoint-badge) | Use a public data source without secrets. |

### 1.2 Beginner workflow

1. Decide whether the value is **fixed**, **live**, or merely **decorative**.
2. Prefer the native provider for authoritative values, such as GitHub for Actions or Codecov for coverage.
3. Open the provider's builder or project dashboard rather than guessing a URL.
4. Copy the raw Markdown and replace every uppercase placeholder.
5. Wrap the badge image in a link to the detailed report, workflow, release, package, documentation, or support page.
6. Preview the README on GitHub and verify both the image and click destination.
7. Add descriptive alternative text and keep the same essential information available as ordinary text.

> External badge and card hosts can change, rate-limit requests, cache old data, or become unavailable. Link to the provider's documentation and avoid making essential instructions depend on a badge.

---

## 2. Badge anatomy

### 2.1 Image-only badge

**Availability:** Portable Markdown image syntax; rendering requires an accessible image host

**Raw source**

```markdown
![Build status](https://img.shields.io/badge/build-passing-brightgreen)
```

**Rendered example**

![Build status](https://img.shields.io/badge/build-passing-brightgreen)

The text inside `[]` is alternative text. The URL inside `()` is the SVG or image returned by the badge host.

### 2.2 Clickable badge

**Availability:** Portable linked-image syntax; rendering and destination require accessible hosts

**Raw source**

```markdown
[![Documentation](https://img.shields.io/badge/docs-open-blue)](https://example.com/)
```

**Rendered example**

[![Documentation](https://img.shields.io/badge/docs-open-blue)](https://example.com/)

The inner `![...](...)` is the badge image. The outer `[...]()` supplies the click destination.

### 2.3 Reference-style badge definitions

**Availability:** Portable reference-link and image syntax

Reference definitions keep long badge URLs away from the visible badge row.

**Raw source**

```markdown
[![Build status][build-badge]][build-details]

[build-badge]: https://img.shields.io/badge/build-passing-brightgreen
[build-details]: https://example.com/builds
```

**Rendered example**

[![Build status][example-build-badge]][example-build-details]

[example-build-badge]: https://img.shields.io/badge/build-passing-brightgreen
[example-build-details]: https://example.com/

Give each definition a clear unique name, especially when a README contains many badges.

---

## 3. Fixed placeholder badges

**Availability:** Shields.io-hosted static images; Markdown embedding itself is portable

Use fixed badges for examples, planned features, manually maintained states, or documentation that must not track a live repository.

### 3.1 Common fixed badges

**Availability:** Shields.io-hosted static images; Markdown embedding itself is portable

**Raw source**

```markdown
![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Downloads](https://img.shields.io/badge/downloads-12k-blue)
![Release](https://img.shields.io/badge/release-v1.2.3-blue)
![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)
![Licence](https://img.shields.io/badge/licence-MIT-yellow)
```

**Rendered example**

![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Downloads](https://img.shields.io/badge/downloads-12k-blue)
![Release](https://img.shields.io/badge/release-v1.2.3-blue)
![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)
![Licence](https://img.shields.io/badge/licence-MIT-yellow)

`%25` is the URL-encoded percent sign used to display `95%`.

### 3.2 Build states

**Availability:** Shields.io-hosted static images; Markdown embedding itself is portable

**Raw source**

```markdown
![Passing](https://img.shields.io/badge/build-passing-brightgreen)
![Failing](https://img.shields.io/badge/build-failing-red)
![Unknown](https://img.shields.io/badge/build-unknown-lightgrey)
```

**Rendered example**

![Passing](https://img.shields.io/badge/build-passing-brightgreen)
![Failing](https://img.shields.io/badge/build-failing-red)
![Unknown](https://img.shields.io/badge/build-unknown-lightgrey)

These are labels only. They do not run a build or verify the stated result.

### 3.3 Platform and runtime labels

**Availability:** Shields.io-hosted static images; Markdown embedding itself is portable

**Raw source**

```markdown
![Windows](https://img.shields.io/badge/Windows-supported-0078D4?logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-supported-000000?logo=apple&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-supported-FCC624?logo=linux&logoColor=black)
![Go](https://img.shields.io/badge/Go-1.24.x-00ADD8?logo=go&logoColor=white)
```

**Rendered example**

![Windows](https://img.shields.io/badge/Windows-supported-0078D4?logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-supported-000000?logo=apple&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-supported-FCC624?logo=linux&logoColor=black)
![Go](https://img.shields.io/badge/Go-1.24.x-00ADD8?logo=go&logoColor=white)

These fixed labels state project policy only. Keep the actual supported-version matrix in ordinary documentation and update both places together.

### 3.4 Documentation, translation, community, and support buttons

**Availability:** Linked Shields.io static images; destinations are service-dependent

**Raw source**

```markdown
[![Documentation](https://img.shields.io/badge/docs-open-blue?logo=readthedocs&logoColor=white)](https://docs.example.com/)
[![Translate](https://img.shields.io/badge/translate-on_Crowdin-2E3340?logo=crowdin&logoColor=white)](https://crowdin.com/project/PROJECT)
[![Discord](https://img.shields.io/badge/community-Discord-5865F2?logo=discord&logoColor=white)](https://discord.gg/INVITE_CODE)
[![Support on Ko-fi](https://img.shields.io/badge/support-Ko--fi-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/ACCOUNT)
```

**Rendered example**

[![Documentation](https://img.shields.io/badge/docs-open-blue?logo=readthedocs&logoColor=white)](https://readthedocs.org/)
[![Translate](https://img.shields.io/badge/translate-on_Crowdin-2E3340?logo=crowdin&logoColor=white)](https://crowdin.com/)
[![Discord](https://img.shields.io/badge/community-Discord-5865F2?logo=discord&logoColor=white)](https://discord.com/)
[![Support on Ko-fi](https://img.shields.io/badge/support-Ko--fi-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/)

The raw destinations are templates. Use the real documentation site, Crowdin project, Discord invite, or support page. Patreon and PayPal can use the same linked static-badge pattern.

---

## 4. Native GitHub Actions status badges

**Availability:** GitHub-specific and workflow-dependent

GitHub provides a native status badge for each Actions workflow. In the repository UI, open **Actions**, select the workflow, then choose **Create status badge** to generate the Markdown.

### 4.1 Default-branch workflow status

**Availability:** GitHub-specific and workflow-dependent

**Raw source**

```markdown
[![CI](https://github.com/OWNER/REPOSITORY/actions/workflows/WORKFLOW_FILE/badge.svg)](https://github.com/OWNER/REPOSITORY/actions/workflows/WORKFLOW_FILE)
```

**Expected on GitHub**

A clickable badge showing the workflow's current passing, failing, or unknown state. Replace `WORKFLOW_FILE` with a real filename such as `ci.yml`.

### 4.2 Specific branch and event

**Availability:** GitHub-specific and workflow-dependent

**Raw source**

```markdown
[![CI on main](https://github.com/OWNER/REPOSITORY/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/OWNER/REPOSITORY/actions/workflows/ci.yml)
```

**Expected on GitHub**

A workflow-status badge filtered to `push` runs on the `main` branch.

> A native workflow badge in a private repository cannot be embedded on an external public site. The workflow filename, branch, and event must match the repository.

---

## 5. Shields.io GitHub repository badges

**Availability:** GitHub data displayed by Shields.io; requires a public or authorised repository API response

These templates query repository data. They are deliberately not rendered here because their values change.

### 5.1 Releases and downloads

**Availability:** GitHub data displayed by Shields.io

**Raw source**

```markdown
![Latest release](https://img.shields.io/github/v/release/OWNER/REPOSITORY?sort=semver)
![Total release downloads](https://img.shields.io/github/downloads/OWNER/REPOSITORY/total)
![Latest release downloads](https://img.shields.io/github/downloads/OWNER/REPOSITORY/latest/total?sort=semver)
```

**Expected on GitHub**

Badges containing the latest GitHub release version and release-asset download totals.

> `sort=semver` selects the latest eligible release by semantic version. Shields.io otherwise defaults to date-based selection for these badges; its builder also exposes prerelease and filtering options. Download badges count GitHub release assets exposed by the Releases API. They are not clone counters, and automatically generated source archives do not behave like ordinary uploaded release assets.

### 5.2 Licence and repository activity

**Availability:** GitHub data displayed by Shields.io

**Raw source**

```markdown
![Licence](https://img.shields.io/github/license/OWNER/REPOSITORY)
![Last commit](https://img.shields.io/github/last-commit/OWNER/REPOSITORY)
![Contributors](https://img.shields.io/github/contributors/OWNER/REPOSITORY)
![Repository size](https://img.shields.io/github/repo-size/OWNER/REPOSITORY)
![Top language](https://img.shields.io/github/languages/top/OWNER/REPOSITORY)
```

**Expected on GitHub**

Badges containing the detected licence, most recent commit date, contributor count, repository size, and top detected language.

### 5.3 Stars, forks, issues, and pull requests

**Availability:** GitHub data displayed by Shields.io

**Raw source**

```markdown
![Stars](https://img.shields.io/github/stars/OWNER/REPOSITORY)
![Forks](https://img.shields.io/github/forks/OWNER/REPOSITORY)
![Open issues](https://img.shields.io/github/issues/OWNER/REPOSITORY)
![Open pull requests](https://img.shields.io/github/issues-pr/OWNER/REPOSITORY)
```

**Expected on GitHub**

Badges containing the repository's current stars, forks, open issues, and open pull-request counts.

### 5.4 Shields.io workflow status

**Availability:** GitHub Actions data displayed by Shields.io

**Raw source**

```markdown
![Workflow status](https://img.shields.io/github/actions/workflow/status/OWNER/REPOSITORY/WORKFLOW_FILE?branch=BRANCH)
```

**Expected on GitHub**

A Shields.io-styled GitHub Actions workflow badge. Prefer GitHub's native workflow badge when no Shields-specific styling is needed.

### 5.5 Directory and file counts

**Availability:** GitHub repository data displayed by Shields.io

**Raw source**

```markdown
![Configuration files](https://img.shields.io/github/directory-file-count/OWNER/REPOSITORY/PATH?type=file&extension=json&label=configuration%20files)
```

**Expected on GitHub**

A count of matching files in `PATH`. Adjust `type`, `extension`, and `label` with the [Shields.io badge builder](https://shields.io/badges). GitHub's directory-content API limits this service to 1,000 items in a directory, so larger counts can be inaccurate; do not use the result as a security or completeness guarantee.

### 5.6 Discord server-count badge

**Availability:** Discord widget data displayed by Shields.io

**Raw source**

```markdown
[![Discord server](https://img.shields.io/discord/SERVER_ID?label=Discord&logo=discord&logoColor=white)](https://discord.gg/INVITE_CODE)
```

**Expected on GitHub**

A clickable Shields.io badge populated from the public Discord server/widget data available for `SERVER_ID`. The server must expose the required widget information, and the invite destination must be valid.

Browse the [Shields.io badge catalogue](https://shields.io/badges) to confirm the current path and available parameters for a specific service.

---

## 6. Package and registry badges

**Availability:** Registry data displayed by Shields.io; exact package names and public visibility are required

### 6.1 npm

**Availability:** npm registry data displayed by Shields.io

**Raw source**

```markdown
![npm version](https://img.shields.io/npm/v/PACKAGE)
![npm monthly downloads](https://img.shields.io/npm/dm/PACKAGE)
```

**Expected on GitHub**

The current npm package version and monthly download count.

### 6.2 PyPI

**Availability:** PyPI registry data displayed by Shields.io

**Raw source**

```markdown
![PyPI version](https://img.shields.io/pypi/v/PACKAGE)
![Supported Python versions](https://img.shields.io/pypi/pyversions/PACKAGE)
```

**Expected on GitHub**

The current PyPI release and Python-version classifiers published by the package.

### 6.3 Docker Hub, crates.io, NuGet, and RubyGems

**Availability:** Public registry data displayed by Shields.io

**Raw source**

```markdown
![Docker pulls](https://img.shields.io/docker/pulls/OWNER/IMAGE)
![crates.io version](https://img.shields.io/crates/v/CRATE)
![NuGet version](https://img.shields.io/nuget/v/PACKAGE)
![RubyGems version](https://img.shields.io/gem/v/GEM)
```

**Expected on GitHub**

Badges populated from the corresponding public registry record.

Always open the relevant entry in the [Shields.io badge catalogue](https://shields.io/badges) before publishing; registry endpoints and optional parameters can change.

---

## 7. Customising Shields.io badges

**Availability:** Shields.io-specific query parameters

### 7.1 Styles

**Availability:** Shields.io-specific query parameters

Supported standard styles currently include `flat`, `flat-square`, `plastic`, `for-the-badge`, and `social`.

**Raw source**

```markdown
![Flat](https://img.shields.io/badge/status-ready-blue?style=flat)
![Flat square](https://img.shields.io/badge/status-ready-blue?style=flat-square)
![Plastic](https://img.shields.io/badge/status-ready-blue?style=plastic)
![For the badge](https://img.shields.io/badge/status-ready-blue?style=for-the-badge)
![Social](https://img.shields.io/badge/status-ready-blue?style=social)
```

**Rendered example**

![Flat](https://img.shields.io/badge/status-ready-blue?style=flat)
![Flat square](https://img.shields.io/badge/status-ready-blue?style=flat-square)
![Plastic](https://img.shields.io/badge/status-ready-blue?style=plastic)
![For the badge](https://img.shields.io/badge/status-ready-blue?style=for-the-badge)
![Social](https://img.shields.io/badge/status-ready-blue?style=social)

### 7.2 Label, colours, and logo

**Availability:** Shields.io-specific query parameters

**Raw source**

```markdown
![Custom badge](https://img.shields.io/badge/status-ready-2ea44f?style=for-the-badge&logo=github&logoColor=white&labelColor=24292f)
```

**Rendered example**

![Custom badge](https://img.shields.io/badge/status-ready-2ea44f?style=for-the-badge&logo=github&logoColor=white&labelColor=24292f)

Useful parameters include:

| Parameter | Purpose |
|---|---|
| `style=` | Badge shape and presentation style |
| `logo=` | A supported [Simple Icons](https://simpleicons.org/) slug |
| `logoColor=` | Logo colour |
| `logoSize=auto` | Adaptively resize some wider Simple Icons logos |
| `label=` | Override the left-side label |
| `labelColor=` | Left-side background colour |
| `color=` | Right-side background colour |
| `cacheSeconds=` | Requested cache lifetime, subject to provider minimums |

For static badge path text, use `_` or `%20` for spaces, `__` for a literal underscore, and `--` for a literal hyphen. URL-encode reserved characters.

Shields.io also documents a `link` query parameter, but it only works when a badge is embedded as an HTML `<object>`. It does not make a Markdown image or HTML `<img>` clickable. For a GitHub README, use the linked-image form `[![alternative text](BADGE_URL)](DESTINATION_URL)` shown above.

### 7.3 Custom logos

**Availability:** Shields.io-specific logo support

Prefer a supported [Simple Icons slug](https://simpleicons.org/) because it keeps the URL readable:

**Raw source**

```markdown
![Readable logo](https://img.shields.io/badge/community-example-blue?logo=discord&logoColor=white)
```

**Rendered example**

![Readable logo](https://img.shields.io/badge/community-example-blue?logo=discord&logoColor=white)

Shields.io also accepts supported custom logo data. A data URI has this general shape:

```text
logo=data:image/svg+xml;base64,BASE64_DATA
```

This can reproduce project-specific branding, but the fully encoded URL is long and difficult to review. Use the [Shields.io logo documentation](https://shields.io/docs/logos), validate the SVG, respect trademark rules, and prefer a separately hosted or repository-owned image when maintainability matters.

---

## 8. Clickable badges and download buttons

### 8.1 Badge linked to a page

**Availability:** Portable linked-image syntax; badge and destination availability are external

**Raw source**

```markdown
[![View releases](https://img.shields.io/badge/releases-view-blue)](https://github.com/OWNER/REPOSITORY/releases)
```

**Rendered example**

[![View releases](https://img.shields.io/badge/releases-view-blue)](https://example.com/)

The rendered example uses a fixed placeholder destination. Replace it with the real repository URL.

### 8.2 Latest release download button

**Availability:** GitHub release URL plus a hosted badge image

**Raw source**

```markdown
[![Download latest](https://img.shields.io/badge/download-latest_release-blue?style=for-the-badge)](https://github.com/OWNER/REPOSITORY/releases/latest/download/ASSET_NAME.zip)
```

**Rendered example**

[![Download latest](https://img.shields.io/badge/download-latest_release-blue?style=for-the-badge)](https://example.com/)

The GitHub destination works only when the latest release contains an uploaded asset whose filename exactly matches `ASSET_NAME.zip`.

---

## 9. Badge rows and alignment

### 9.1 Ordinary Markdown row

**Availability:** Portable Markdown + GitHub

**Raw source**

```markdown
![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Release](https://img.shields.io/badge/release-v1.2.3-blue)
![Licence](https://img.shields.io/badge/licence-MIT-yellow)
```

**Rendered example**

![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Release](https://img.shields.io/badge/release-v1.2.3-blue)
![Licence](https://img.shields.io/badge/licence-MIT-yellow)

Adjacent Markdown images normally appear on one row while enough horizontal space remains, then wrap naturally.

### 9.2 Centred HTML row

**Availability:** GitHub-supported HTML; not portable Markdown layout syntax

**Raw source**

```html
<p align="center">
  <img alt="Build passing" src="https://img.shields.io/badge/build-passing-brightgreen">
  <img alt="Release v1.2.3" src="https://img.shields.io/badge/release-v1.2.3-blue">
  <img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-yellow">
</p>
```

**Rendered example**

<p align="center">
  <img alt="Build passing" src="https://img.shields.io/badge/build-passing-brightgreen">
  <img alt="Release v1.2.3" src="https://img.shields.io/badge/release-v1.2.3-blue">
  <img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-yellow">
</p>

GitHub retains the legacy `align` attribute today, but custom CSS, `style`, and classes are not available for arbitrary README styling.

---

## 10. Dynamic JSON and endpoint badges

### 10.1 Extract a value from public JSON

**Availability:** Shields.io dynamic JSON service; the JSON URL must be publicly reachable

**Raw source**

```markdown
![Version from JSON](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fexample.com%2Fdata.json&query=%24.version&label=version&color=blue)
```

**Expected on GitHub**

Shields.io fetches the JSON document, evaluates the JSONPath query `$.version`, and displays the resulting value.

The example URL is illustrative. Use the [dynamic JSON badge builder](https://shields.io/badges/dynamic-json-badge) to encode the source URL and query safely.

### 10.2 Custom endpoint response

**Availability:** Shields.io endpoint service plus a user-controlled public JSON endpoint

**Raw endpoint response**

```json
{
  "schemaVersion": 1,
  "label": "status",
  "message": "ready",
  "color": "2ea44f"
}
```

**Raw Markdown source**

```markdown
![Custom endpoint](https://img.shields.io/endpoint?url=https%3A%2F%2Fexample.com%2Fbadge.json)
```

**Expected on GitHub**

A badge showing `status | ready`. The endpoint must return the documented Shields.io schema and an appropriate JSON content type.

See the [endpoint badge schema and builder](https://shields.io/badges/endpoint-badge).

---

## 11. Coverage and security badges

### 11.1 Codecov

**Availability:** Third-party repository integration

**Raw source**

```markdown
[![Coverage](https://codecov.io/github/OWNER/REPOSITORY/graph/badge.svg?branch=BRANCH)](https://app.codecov.io/github/OWNER/REPOSITORY)
```

**Expected on GitHub**

A clickable Codecov coverage badge for the configured branch. Generate the exact badge in Codecov's **Badges & Graphs** area.

> Do not paste a private-repository badge token into public documentation. Follow [Codecov's private-badge guidance](https://docs.codecov.com/docs/status-badges) for the intended visibility.

### 11.2 Coveralls

**Availability:** Third-party repository integration

**Raw source**

```markdown
[![Coverage Status](https://coveralls.io/repos/github/OWNER/REPOSITORY/badge.svg?branch=BRANCH)](https://coveralls.io/github/OWNER/REPOSITORY?branch=BRANCH)
```

**Expected on GitHub**

A clickable Coveralls coverage badge after the repository and branch are configured with Coveralls. Use the badge provided by the [Coveralls dashboard and documentation](https://docs.coveralls.io/).

### 11.3 OpenSSF Scorecard

**Availability:** Third-party security service; published Scorecard results required

**Raw source**

```markdown
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/OWNER/REPOSITORY/badge)](https://scorecard.dev/viewer/?uri=github.com/OWNER/REPOSITORY)
```

**Expected on GitHub**

A clickable security-health score after the repository's Scorecard workflow enables `publish_results: true`.

### 11.4 Read the Docs build status

**Availability:** Third-party documentation build integration

**Raw source**

```markdown
[![Documentation Status](https://readthedocs.org/projects/PROJECT/badge/?version=latest)](https://PROJECT.readthedocs.io/en/latest/?badge=latest)
```

**Expected on GitHub**

A clickable documentation build-status badge for the configured Read the Docs project and version. Copy the exact markup from the [Read the Docs badge documentation](https://docs.readthedocs.com/platform/stable/badges.html).

### 11.5 SonarQube Cloud or Server project badges

**Availability:** Third-party project integration

**Raw source**

```markdown
[![Quality Gate Status](SONAR_BADGE_URL)](SONAR_PROJECT_OVERVIEW_URL)
```

**Expected on GitHub**

A clickable quality-gate or project-metric badge generated by the Sonar project UI. Copy the provider-generated Markdown from [SonarQube Cloud](https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/managing-your-project-as-developer) or [SonarQube Server](https://docs.sonarsource.com/sonarqube-server/user-guide/project-badge); do not invent or publish a general API token.

---

## 12. Profile cards, icons, and decorative widgets

These are community-hosted SVG services, not native GitHub UI. Use them selectively and keep essential information in ordinary text.

### 12.1 GitHub Readme Stats

**Availability:** Third-party and account-dependent

**Raw source**

```markdown
![GitHub statistics](GITHUB_README_STATS_URL/api?username=USERNAME&show_icons=true&theme=default)
```

**Expected on GitHub**

A generated profile-statistics card for `USERNAME`. Replace `GITHUB_README_STATS_URL` with a working deployment. The widely copied public Vercel deployment was paused when this guide was reviewed, so follow the [GitHub Readme Stats project and self-hosting guidance](https://github.com/anuraghazra/github-readme-stats) for the current endpoint instead of assuming an old example URL still works.

### 12.2 Skill Icons

**Availability:** Third-party fixed icon service

**Raw source**

```markdown
[![Example skills](https://skillicons.dev/icons?i=git,python,javascript&theme=light)](https://skillicons.dev)
```

**Rendered example**

[![Example skills](https://skillicons.dev/icons?i=git,python,javascript&theme=light)](https://skillicons.dev)

The icon list is fixed by the `i=` parameter and does not measure account activity. See the [Skill Icons source and icon list](https://github.com/tandpfun/skill-icons).

### 12.3 Readme Typing SVG

**Availability:** Third-party decorative SVG service

**Raw source**

```markdown
[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&pause=1000&width=435&lines=Example+placeholder+text)](https://readme-typing-svg.demolab.com/)
```

**Rendered example**

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&pause=1000&width=435&lines=Example+placeholder+text)](https://readme-typing-svg.demolab.com/)

The text is fixed in the URL and does not track repository data. Build the URL with the [Readme Typing SVG generator](https://readme-typing-svg.demolab.com/).

### 12.4 Streak and trophy cards

**Availability:** Third-party and account-dependent

**Raw source**

```markdown
![GitHub streak](https://github-readme-streak-stats.herokuapp.com/?user=USERNAME)

![GitHub trophies](PROFILE_TROPHY_URL/?username=USERNAME)
```

**Expected on GitHub**

Cards generated from the public activity of `USERNAME`. Configure the first through [GitHub Readme Streak Stats](https://github-readme-streak-stats.herokuapp.com/). Replace `PROFILE_TROPHY_URL` with a working deployment from the [GitHub Profile Trophy project](https://github.com/ryo-ma/github-profile-trophy); the older public Vercel deployment was disabled when this guide was reviewed.

> Contribution-derived cards may use different counting rules, caches, and API scopes from GitHub's own profile interface. Treat them as decorative summaries rather than authoritative audit records.

---

## 13. GitHub-safe README UI elements

GitHub sanitises rendered HTML. Arbitrary JavaScript, CSS, forms, iframes, and event handlers are unavailable. The most useful UI-like patterns are links, images, badges, tables, `<details>`, and theme-aware `<picture>` elements.

### 13.1 Collapsible section

**Availability:** GitHub-supported HTML

**Raw source**

```html
<details>
<summary>Show installation notes</summary>

- First placeholder step
- Second placeholder step

</details>
```

**Rendered example**

<details>
<summary>Show installation notes</summary>

- First placeholder step
- Second placeholder step

</details>

### 13.2 Badge table

**Availability:** GFM table plus hosted images

**Raw source**

```markdown
| Area | Status |
|---|---|
| Build | ![Build](https://img.shields.io/badge/build-passing-brightgreen) |
| Coverage | ![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen) |
| Release | ![Release](https://img.shields.io/badge/release-v1.2.3-blue) |
```

**Rendered example**

| Area | Status |
|---|---|
| Build | ![Build](https://img.shields.io/badge/build-passing-brightgreen) |
| Coverage | ![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen) |
| Release | ![Release](https://img.shields.io/badge/release-v1.2.3-blue) |

### 13.3 Theme-aware cards and images

**Availability:** GitHub-supported HTML and GitHub theme fragments

Use a `<picture>` block when a provider supplies separate light and dark image URLs. See the [theme-aware image example](md-and-gh-cheat-sheet.md#114-theme-aware-images) and the [rendered responsive-image example](md-and-gh-cheat-sheet.md#149-responsive-images-and-ruby-annotations) in the main cheat sheet.

### 13.4 Repository banners, logos, screenshots, and previews

**Availability:** Portable image syntax or GitHub-supported HTML; the image must be accessible

For durable project documentation, commit the image to the repository and use a relative path.

**Raw source**

```markdown
![Project interface preview](assets/project-preview.png)
```

```html
<p align="center">
  <a href="https://example.com/">
    <img src="assets/project-banner.svg" alt="Project name" width="720">
  </a>
</p>
```

**Expected on GitHub**

The first example renders a repository-owned screenshot. The second renders a centred, explicitly sized banner that links to the project site. The paths are illustrative and require real files.

| Image source | When to use it | Guidance |
|---|---|---|
| Repository-relative file such as `assets/banner.svg` | Project logos, screenshots, diagrams, and stable documentation | Preferred for versioning and forks. |
| GitHub's issue/comment/file uploader | Quick screenshots and discussion attachments | GitHub supplies an anonymised asset URL; see [Attaching files](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files). |
| Provider-hosted SVG or PNG | Badges, coverage reports, community widgets, and service buttons | Link to the provider and document the dependency. |
| External image host such as Imgur | Existing externally hosted screenshots | Less durable than repository-owned assets; keep a recoverable source copy. |
| `raw.githubusercontent.com` URL | Direct access to an existing repository file | A relative link is normally clearer inside the same repository. |

GitHub may retain `width` and `height` attributes, but it strips arbitrary inline `style`. Use `width="720"` instead of `style="width: 70%"` in new README markup.

### 13.5 Styled code screenshots

**Availability:** External image-generation tool plus an ordinary Markdown image

Tools such as [Carbon](https://carbon.now.sh/) can export a styled code image.

**Raw source**

```markdown
![Example configuration code](assets/configuration-example.png)
```

**Expected on GitHub**

A repository-owned image exported from the chosen tool. Include the real code in a fenced code block nearby so it remains searchable, selectable, copyable, and accessible.

### 13.6 Support and community buttons

**Availability:** Linked images; destination and branding are service-dependent

Use the linked static-badge pattern from section 3.4 for Discord, Crowdin, Ko-fi, Patreon, PayPal, documentation, or a project website. When a service supplies an official image button, preserve useful `alt` text and link only to the genuine service page.

### 13.7 Native GitHub Sponsor button

**Availability:** GitHub repository setting; rendered in repository chrome rather than README content

GitHub can place a **Sponsor** button beside the repository controls. Configure it with `.github/FUNDING.yml` on the default branch.

**Raw source**

```yaml
github: [GITHUB_SPONSOR_USERNAME]
ko_fi: KOFI_USERNAME
patreon: PATREON_USERNAME
custom:
  - "https://example.com/support"
```

**Expected on GitHub**

A native repository-header funding menu containing the configured destinations. This is not Markdown and does not render inside the README. Use only supported funding platforms and follow GitHub's [Sponsor button documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository) for the current keys and limits.

---

## 14. Limitations, accessibility, and maintenance

1. **Use meaningful alternative text.** `![Build passing](...)` is more useful than `![](...)`.
2. **Do not rely on colour alone.** Include words such as `passing`, `failing`, or `unknown`.
3. **Prefer native sources for authoritative status.** Use GitHub's native workflow badge for Actions unless Shields.io styling is specifically needed.
4. **Keep placeholders obvious.** Replace uppercase template fields before publishing.
5. **Check every link.** A badge can render while its click destination is broken or misleading.
6. **Expect caching.** Badge hosts and GitHub's image proxy may delay visible updates.
7. **Limit visual noise.** A small group of meaningful badges is easier to scan than a wall of counters.
8. **Treat external hosts as dependencies.** If the host fails, the image fails; keep important values in accessible text elsewhere.
9. **Do not expose secrets.** Never put API keys, personal access tokens, private badge tokens, or signed private URLs into public Markdown.
10. **Review third-party services.** Read their source, privacy policy, rate limits, and self-hosting guidance before embedding them.
11. **Do not fake live status.** Clearly label fixed badges as examples, plans, manual states, or placeholders.
12. **Avoid unreliable visitor counters.** Image proxying and caching can make view counts ambiguous or misleading.

GitHub proxies external images through anonymised URLs. This protects visitors but can also make updated badge images appear stale. See GitHub's [About anonymised URLs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-anonymized-urls).

### Common failures

| Badge output or symptom | Likely cause | What to check |
|---|---|---|
| `not found` | Incorrect owner, repository, workflow, package, branch, path, or private data | Reopen the provider's builder and verify every placeholder. |
| `no releases` | No eligible GitHub release, or release-selection filters exclude it | Check releases, prereleases, and date-versus-SemVer selection. |
| `unknown` | The provider has no result for the requested branch, workflow, package, or coverage upload | Open the detailed provider page and confirm the default branch and latest run/upload. |
| Stale value | Upstream caching, Shields.io caching, or GitHub's image proxy | Wait for the documented cache period and avoid cache-busting every README view. |
| Broken logo | Invalid, renamed, removed, or not-yet-synchronised Simple Icons slug | Search [Simple Icons](https://simpleicons.org/) and check [Shields.io logo guidance](https://shields.io/docs/logos). |
| Badge renders but clicking fails | The image URL is valid but the outer link destination is wrong | Test the image and destination separately. |
| Private metric is blank | The public image host cannot authenticate to the private source | Use the provider's purpose-built private-badge option; never expose a general token. |

---

## 15. Compact templates

```markdown
<!-- Fixed placeholder badge -->
![Build](https://img.shields.io/badge/build-passing-brightgreen)

<!-- Clickable fixed badge -->
[![Documentation](https://img.shields.io/badge/docs-open-blue)](https://example.com/docs)

<!-- Native GitHub Actions workflow badge -->
[![CI](https://github.com/OWNER/REPOSITORY/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPOSITORY/actions/workflows/ci.yml)

<!-- Dynamic GitHub release and download badges -->
![Release](https://img.shields.io/github/v/release/OWNER/REPOSITORY?sort=semver)
![Downloads](https://img.shields.io/github/downloads/OWNER/REPOSITORY/total)

<!-- Package badge -->
![npm](https://img.shields.io/npm/v/PACKAGE)

<!-- Latest release asset button -->
[![Download](https://img.shields.io/badge/download-latest_release-blue?style=for-the-badge)](https://github.com/OWNER/REPOSITORY/releases/latest/download/ASSET_NAME.zip)
```

---

## 16. Sources

### GitHub

- [Adding a workflow status badge](https://docs.github.com/actions/managing-workflow-runs/adding-a-workflow-status-badge)
- [Basic writing and formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)
- [About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [Linking to releases](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases)
- [About profile READMEs](https://docs.github.com/en/account-and-profile/concepts/personal-profile)
- [Attaching files](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files)
- [About anonymised image URLs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-anonymized-urls)
- [Displaying a sponsor button in your repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository)

### Badge, icon, coverage, and security providers

- [Shields.io documentation](https://shields.io/docs/)
- [Shields.io badge catalogue](https://shields.io/badges)
- [Shields.io static badge builder](https://shields.io/badges/static-badge)
- [Shields.io dynamic JSON badge builder](https://shields.io/badges/dynamic-json-badge)
- [Shields.io endpoint badge builder](https://shields.io/badges/endpoint-badge)
- [Shields.io logo documentation](https://shields.io/docs/logos)
- [Simple Icons](https://simpleicons.org/)
- [Simple Icons source and CDN usage](https://github.com/simple-icons/simple-icons)
- [Codecov status badges](https://docs.codecov.com/docs/status-badges)
- [Coveralls documentation](https://docs.coveralls.io/)
- [OpenSSF Scorecard badges](https://github.com/ossf/scorecard#scorecard-badges)
- [Read the Docs badges](https://docs.readthedocs.com/platform/stable/badges.html)
- [SonarQube Cloud project badges](https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/managing-your-project-as-developer)
- [SonarQube Server project badges](https://docs.sonarsource.com/sonarqube-server/user-guide/project-badge)

### Community README card and widget projects

- [GitHub Readme Stats](https://github.com/anuraghazra/github-readme-stats)
- [Skill Icons](https://skillicons.dev/) and [source repository](https://github.com/tandpfun/skill-icons)
- [Readme Typing SVG generator](https://readme-typing-svg.demolab.com/) and [source repository](https://github.com/DenverCoder1/readme-typing-svg)
- [GitHub Readme Streak Stats generator](https://github-readme-streak-stats.herokuapp.com/) and [source repository](https://github.com/DenverCoder1/github-readme-streak-stats)
- [GitHub Profile Trophy](https://github.com/ryo-ma/github-profile-trophy)

### README, badge, icon, and image builders

- [readme.so](https://readme.so/)
- [GitHub Profile README Generator](https://rahuldkjain.github.io/gh-profile-readme-generator/) and [source repository](https://github.com/rahuldkjain/github-profile-readme-generator)
- [Badgen](https://badgen.net/)
- [For the Badge](https://forthebadge.com/)
- [Devicon](https://devicon.dev/) and [source repository](https://github.com/devicons/devicon)
- [Carbon](https://carbon.now.sh/)
- [Crowdin](https://crowdin.com/)
- [Ko-fi](https://ko-fi.com/), [Patreon](https://www.patreon.com/), and [PayPal](https://www.paypal.com/)
