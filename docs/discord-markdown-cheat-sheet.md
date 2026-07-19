# Complete Discord Markdown & Message Formatting Cheat Sheet

> **Reviewed against official Discord documentation:** 19 July 2026<br>
> **Scope:** Discord desktop, web, and mobile message formatting, plus Discord-specific message tokens used by users, bots, and webhooks.

Discord uses a **subset of Markdown**, then adds several Discord-only features such as underline, spoilers, subtext, mentions, custom emoji, dynamic timestamps, guild-navigation links, and silent messages.

This reference deliberately shows most features in two forms:

1. **Source** — the literal characters to type or copy.
2. **Applied example** — a representative rendering; exact appearance and interaction can vary by Discord client.

> IDs, filenames, command names, paths, domains, and timestamps used in examples are illustrative placeholders unless the text explicitly identifies them as real resources. Replace them before sending or implementing the example.

Availability labels used throughout this guide:

- **Portable Markdown + Discord:** works as ordinary Markdown syntax and in Discord messages, subject to the stated Discord subset and client caveats.
- **Markdown extension + Discord:** works in Discord and in Markdown renderers that support the named extension, but is not portable CommonMark.
- **Discord-only syntax or token:** a Discord extension rather than portable Markdown.
- **Discord client-dependent:** observed rendering or interaction can vary across desktop, web, iOS, and Android.
- **Discord API-only:** configured through an app, bot, or webhook message payload—such as embed/message flags, `allowed_mentions`, or attachment/component fields—rather than literal user-facing Markdown.
- **Markdown feature not reliable in Discord:** valid elsewhere, but unsupported, undocumented, or unsuitable to depend on in Discord messages.

> [!IMPORTANT]
> A normal Markdown viewer, GitHub, or text editor may not preview Discord-only features correctly. Test Discord-only syntax in a private Discord channel or DM.

This guide distinguishes between:

- **Officially documented** syntax in Discord Support or the Discord Developer documentation.
- **Client-observed** behaviour that Discord does not guarantee across desktop, web, iOS, and Android.
- **API controls** for apps, bots, and webhooks that are not literal user-facing Markdown.

No document can honestly guarantee undocumented client behaviour forever. Anything not covered by Discord's public documentation is labelled and should be tested in the target client.

---

## Table of contents

- [1. Quick-reference table](#1-quick-reference-table)
- [2. Basic text styles](#2-basic-text-styles)
- [3. Combined text styles](#3-combined-text-styles)
- [4. Headers](#4-headers)
- [5. Discord subtext](#5-discord-subtext)
- [6. Paragraphs and line breaks](#6-paragraphs-and-line-breaks)
- [7. Lists](#7-lists)
- [8. Block quotes](#8-block-quotes)
- [9. Inline code](#9-inline-code)
- [10. Multiline code blocks](#10-multiline-code-blocks)
- [11. Code-block language tags](#11-code-block-language-tags)
- [12. Diff and ANSI colour blocks](#12-diff-and-ansi-colour-blocks)
- [13. Links and embed control](#13-links-and-embed-control)
- [14. Spoilers](#14-spoilers)
- [15. Escaping Markdown](#15-escaping-markdown)
- [16. Discord mentions and entity markup](#16-discord-mentions-and-entity-markup)
- [17. Discord timestamps](#17-discord-timestamps)
- [18. Custom emoji markup](#18-custom-emoji-markup)
- [19. Slash-command mentions](#19-slash-command-mentions)
- [20. Guild-navigation links](#20-guild-navigation-links)
- [21. Silent messages](#21-silent-messages)
- [22. Features not documented or not reliable in Discord](#22-features-not-documented-or-not-reliable-in-discord)
- [23. Common formatting mistakes](#23-common-formatting-mistakes)
- [24. Full demonstration message](#24-full-demonstration-message)
- [25. Sources and maintenance notes](#25-sources-and-maintenance-notes)

---

# 1. Quick-reference table

| Feature | Source syntax | Availability |
|---|---|---|
| Italic | `*text*` or `_text_` | Markdown + Discord |
| Bold | `**text**` | Markdown + Discord |
| Bold italic | `***text***` | Markdown + Discord |
| Underline | `__text__` | Discord-only |
| Underline italic | `__*text*__` | Discord-only |
| Underline bold | `__**text**__` | Discord-only |
| Underline bold italic | `__***text***__` | Discord-only |
| Strikethrough | `~~text~~` | Markdown extension + Discord |
| Spoiler | `\|\|text\|\|` | Discord-only |
| Spoiler command | `/spoiler Message` | Discord client shortcut |
| Large header | `# Text` | Markdown + Discord; levels 1–3 only |
| Medium header | `## Text` | Markdown + Discord; levels 1–3 only |
| Small header | `### Text` | Markdown + Discord; levels 1–3 only |
| Subtext | `-# Text` | Discord-only |
| Bullet list | `- Item` or `* Item` | Markdown + Discord |
| Numbered list | `1. Item` | Markdown + Discord |
| Single-line quote | `> Text` | Markdown + Discord |
| Multi-line quote | `>>> Text` | Discord-only variation |
| Inline code | `` `code` `` | Markdown + Discord |
| Code block | Triple backticks | Markdown + Discord |
| Masked link | `[label](https://example.com)` | Markdown + Discord |
| Suppress one link embed | `<https://example.com>` | Discord-specific behaviour |
| User mention | `<@USER_ID>` | Discord-only token |
| Channel mention | `<#CHANNEL_ID>` | Discord-only token |
| Role mention | `<@&ROLE_ID>` | Discord-only token |
| Timestamp | `<t:UNIX_TIMESTAMP:STYLE>` | Discord-only token |
| Custom emoji | `<:NAME:EMOJI_ID>` | Discord-only token |
| Animated emoji | `<a:NAME:EMOJI_ID>` | Discord-only token |
| Slash-command mention | `</name:COMMAND_ID>` | Discord-only token |
| Guild navigation | `<id:TYPE>` | Discord-only token |
| Silent message | `@silent Message` | Discord client-dependent |

> The backslashes in the spoiler cell (`\|\|text\|\|`) only escape the pipe characters so this Markdown table is not split into extra columns. The rendered cell shows `||text||`; type the Discord spoiler itself **without** backslashes.

---

# 2. Basic text styles

## 2.1 Italic with asterisks

**Availability:** Portable Markdown + Discord

**Source**

```text
*This text is italic.*
```

**Applied example**

*This text is italic.*

---

## 2.2 Italic with underscores

**Availability:** Portable Markdown + Discord

**Source**

```text
_This text is also italic._
```

**Applied example**

_This text is also italic._

> Underscores inside filenames or identifiers can trigger unwanted italics. For technical text, use inline code: `` `file_name.txt` ``.

---

## 2.3 Bold

**Availability:** Portable Markdown + Discord

**Source**

```text
**This text is bold.**
```

**Applied example**

**This text is bold.**

> Discord bold uses double **asterisks**. In Discord, double underscores are underline—not the usual Markdown alternative for bold.

---

## 2.4 Bold italic

**Availability:** Portable Markdown + Discord

**Source**

```text
***This text is bold and italic.***
```

**Applied example**

***This text is bold and italic.***

---

## 2.5 Underline — Discord behaviour

**Availability:** Discord-only syntax

**Source**

```text
__This text is underlined.__
```

**Expected in Discord**

__This text is underlined.__

> [!NOTE]
> This is a Discord-specific interpretation. In some other Markdown systems, double underscores may mean **bold** instead.

---

## 2.6 Strikethrough

**Availability:** Markdown extension + Discord (GFM-style strikethrough; not CommonMark)

**Source**

```text
~~This text is crossed out.~~
```

**Applied example**

~~This text is crossed out.~~

---

## 2.7 Spoiler — Discord-only

**Availability:** Discord-only syntax

**Source**

```text
||This text is hidden until revealed.||
```

**Expected in Discord**

The text appears behind an interactive spoiler cover until the viewer reveals it. The exact interaction can vary by client and input method.

> A normal Markdown viewer may display the `||` characters literally.

---

# 3. Combined text styles

Discord lets you nest compatible markers. Keep the opening and closing markers properly balanced.

## 3.1 Underline italic

**Availability:** Discord-only combined syntax

**Source**

```text
__*Underlined and italic*__
```

**Expected in Discord**

Underlined italic text.

---

## 3.2 Underline bold

**Availability:** Discord-only combined syntax

**Source**

```text
__**Underlined and bold**__
```

**Expected in Discord**

Underlined bold text.

---

## 3.3 Underline bold italic

**Availability:** Discord-only combined syntax

**Source**

```text
__***Underlined, bold, and italic***__
```

**Expected in Discord**

Underlined bold-italic text.

---

## 3.4 Bold strikethrough

**Availability:** Markdown extension + Discord; this combined rendering is client-dependent

> **Client-observed combination:** Discord officially documents bold and strikethrough separately, but not every possible nesting combination. Test combinations when cross-client consistency matters.

**Source**

```text
**~~Bold and crossed out~~**
```

**Applied example**

**~~Bold and crossed out~~**

---

## 3.5 Italic strikethrough

**Availability:** Markdown extension + Discord; this combined rendering is client-dependent

**Source**

```text
*~~Italic and crossed out~~*
```

**Applied example**

*~~Italic and crossed out~~*

---

## 3.6 Underline strikethrough

**Availability:** Discord-only combined syntax

**Source**

```text
__~~Underlined and crossed out~~__
```

**Expected in Discord**

Underlined strikethrough text.

---

## 3.7 Bold italic strikethrough

**Availability:** Markdown extension + Discord; this combined rendering is client-dependent

**Source**

```text
***~~Bold, italic, and crossed out~~***
```

**Applied example**

***~~Bold, italic, and crossed out~~***

---

## 3.8 Styled spoiler

**Availability:** Discord-only combined syntax

Formatting can be placed inside spoiler markers.

**Source**

```text
||**Bold secret** and *italic secret*||
```

**Expected in Discord**

A hidden spoiler that reveals bold and italic text when the viewer activates it. The exact interaction depends on the client and input method.

---

## 3.9 Inline code does not process inner Markdown

**Availability:** Portable Markdown + Discord

**Source**

```text
`**This remains literal and is not bold.**`
```

**Applied example**

`**This remains literal and is not bold.**`

---

# 4. Headers

Discord supports **three** hash-style header levels. Standard Markdown can support up to six, but Discord only documents and renders `#`, `##`, and `###` as headers.

The hash characters must be at the **beginning of a new line**, followed by a space.

## 4.1 Level-one header

**Availability:** Portable Markdown + Discord; Discord supports only heading levels 1–3

**Source**

```text
# Large Header
```

**Applied example**

# Large Header

---

## 4.2 Level-two header

**Availability:** Portable Markdown + Discord; Discord supports only heading levels 1–3

**Source**

```text
## Medium Header
```

**Applied example**

## Medium Header

---

## 4.3 Level-three header

**Availability:** Portable Markdown + Discord; Discord supports only heading levels 1–3

**Source**

```text
### Small Header
```

**Applied example**

### Small Header

---

## 4.4 Formatting inside headers

**Availability:** Portable Markdown; nested formatting in Discord headers is client-dependent

> **Client-observed behaviour:** Discord officially documents the three header levels, but does not publish a compatibility matrix for formatting nested inside a header.

**Source**

```text
## **Bold**, *italic*, and `code` in a header
```

**Applied example**

## **Bold**, *italic*, and `code` in a header

> Headers are already visually bold, so adding `**bold**` may not produce much extra difference.

---

## 4.5 Header requirements

**Availability:** Portable Markdown + Discord; Discord supports only heading levels 1–3

Works:

```text
## Correct Header
```

Does not work as a header:

```text
##No space
Text before ## Not at the start
    ## Indented
#### Discord does not support a fourth header level
```

---

# 5. Discord subtext

Subtext is **unique to Discord**. It produces a smaller, dimmer line suitable for IDs, timestamps, notes, or secondary details.

It must begin a new line with `-#` followed by a space.

## 5.1 Basic subtext

**Availability:** Discord-only syntax

**Source**

```text
-# This appears smaller and dimmer in Discord.
```

**Expected in Discord**

A small grey/dim line of text.

---

## 5.2 Subtext with inline code

**Availability:** Discord-only syntax

**Source**

```text
-# User ID: `123456789012345678`
```

**Expected in Discord**

Small dim text, with the numeric ID displayed as inline code.

---

## 5.3 Subtext with styling

**Availability:** Discord-only syntax

**Source**

```text
-# **Important secondary note** with `code`
```

**Expected in Discord**

Small secondary text containing bold and inline-code formatting.

---

## 5.4 Subtext requirements

**Availability:** Discord-only syntax

Works:

```text
-# Correct subtext
```

Does not work:

```text
-#No space
Text before -# not at the start
  -# Indented subtext
```

---

# 6. Paragraphs and line breaks

Discord does not rely on normal Markdown “hard line break” syntax. Use the Discord editor to insert a new line.

- **Desktop/web:** `Shift + Enter` normally inserts a new line without sending.
- **Mobile:** use the keyboard’s line-break/return key.
- A blank line separates sections visually.

## 6.1 New lines

**Availability:** Portable text layout + Discord

**Source**

```text
First line
Second line

New paragraph-like section
```

**Expected in Discord**

First line\
Second line

New paragraph-like section

> Two trailing spaces, `<br>`, and other Markdown/HTML line-break tricks are not needed and may not work as expected in Discord.

---

# 7. Lists

Discord officially documents unordered lists using `-` or `*`, ordered lists using a number followed by `.`, and nested lists using indentation.

Put a space after the marker.

## 7.1 Hyphen bullet list

**Availability:** Portable Markdown + Discord

**Source**

```text
- First item
- Second item
- Third item
```

**Applied example**

- First item
- Second item
- Third item

---

## 7.2 Asterisk bullet list

**Availability:** Portable Markdown + Discord

**Source**

```text
* First item
* Second item
* Third item
```

**Applied example**

* First item
* Second item
* Third item

---

## 7.3 Numbered list

**Availability:** Portable Markdown + Discord

**Source**

```text
1. First item
2. Second item
3. Third item
```

**Applied example**

1. First item
2. Second item
3. Third item

---

## 7.4 Automatic numbering

**Availability:** Discord client-dependent numbering behaviour

> **Client-observed behaviour:** Discord does not document ordered-list normalisation. Current clients may number repeated `1.` markers sequentially, but do not rely on this without testing the target client.

**Source**

```text
1. First item
1. Second item
1. Third item
```

**Possible current-client result**

A sequential numbered list.

---

## 7.5 Starting at another number

**Availability:** Discord client-dependent numbering behaviour

> **Client-observed behaviour:** Discord does not document whether an ordered list must begin with `1.` or preserve another starting number.

**Source**

```text
5. Fifth item
6. Sixth item
7. Seventh item
```

**Possible current-client result**

An ordered list beginning at or displaying the detected starting number, depending on the current client renderer.

---

## 7.6 Nested unordered list

**Availability:** Portable Markdown + Discord

Discord’s official guide demonstrates **two spaces** before the nested marker.

**Source**

```text
- Parent item
  - Child item
  - Another child
- Second parent
```

**Applied example**

- Parent item
  - Child item
  - Another child
- Second parent

---

## 7.7 Mixed nested list

**Availability:** Portable Markdown; mixed nested-list rendering in Discord is client-dependent

Discord's official guide demonstrates two-space indentation for nested `-` and `*` bullets. Mixed ordered/unordered nesting is client-observed and should be tested.

**Source**

```text
1. First category
  - Detail A
  - Detail B
2. Second category
  1. Nested numbered item
  2. Another nested item
```

**Expected in Discord**

A numbered parent list with nested bullet and numbered entries.

---

## 7.8 Formatting inside list items

**Availability:** Portable Markdown + Discord

**Source**

```text
- **Bold item**
- *Italic item*
- `Code item`
- [Linked item](https://example.com)
```

**Applied example**

- **Bold item**
- *Italic item*
- `Code item`
- [Linked item](https://example.com)

---

## 7.9 Prevent accidental list formatting

**Availability:** Portable Markdown + Discord

**Source**

```text
\- This remains a literal hyphen.
1\. This remains literal text instead of a numbered item.
```

**Applied example**

\- This remains a literal hyphen.\
1\. This remains literal text instead of a numbered item.

---

# 8. Block quotes

## 8.1 Single quoted line

**Availability:** Portable Markdown + Discord

Use `>` followed by a space.

**Source**

```text
> This is a quoted line.
```

**Applied example**

> This is a quoted line.

---

## 8.2 Several separately marked quoted lines

**Availability:** Portable Markdown + Discord

**Source**

```text
> First quoted line
> Second quoted line
> Third quoted line
```

**Applied example**

> First quoted line
> Second quoted line
> Third quoted line

---

## 8.3 Quote the rest of the message with `>>>`

**Availability:** Discord-only multiline quote syntax

Discord officially supports `>>>` in **ordinary message content**. It is not limited to embeds.

Place `>>>` followed by a space before the first line. Discord then treats that line and the remaining lines in the same message as one multi-line block quote.

**Source**

```text
>>> This begins a multi-line quote.
This line is also part of the quote.
So is this line.
```

**Expected in Discord**

Every remaining line in that Discord message appears inside the quote.

> [!WARNING]
> Put content that must remain outside the quote **before** `>>>`, because `>>>` consumes the remainder of the message.

---

## 8.4 Styling inside a quote

**Availability:** Portable Markdown + Discord

Basic inline formatting normally works inside a quoted line.

**Source**

```text
> **Important:** use `code` and *emphasis* inside quotes.
```

**Applied example**

> **Important:** use `code` and *emphasis* inside quotes.

---

## 8.5 Prevent quote formatting

**Availability:** Portable Markdown + Discord

**Source**

```text
\> This displays a literal greater-than symbol.
```

**Applied example**

\> This displays a literal greater-than symbol.

---

# 9. Inline code

Inline code uses one backtick on each side.

## 9.1 Basic inline code

**Availability:** Portable Markdown + Discord

**Source**

```text
Run the `example-action` command.
```

**Applied example**

Run the `example-action` command.

---

## 9.2 Inline paths, commands, and IDs

**Availability:** Portable Markdown + Discord

**Source**

```text
Edit `config.toml`, run `pnpm install`, and copy user ID `123456789012345678`.
```

**Applied example**

Edit `config.toml`, run `pnpm install`, and copy user ID `123456789012345678`.

---

## 9.3 Markdown is disabled inside inline code

**Availability:** Portable Markdown + Discord

**Source**

```text
`**not bold**`, `||not a spoiler||`, and `<@123456789012345678>`
```

**Applied example**

`**not bold**`, `||not a spoiler||`, and `<@123456789012345678>`

---

## 9.4 Put a backtick inside inline code

**Availability:** Portable CommonMark code-span syntax; test this delimiter in the target Discord client

> **Client-observed behaviour:** Discord's public guide documents ordinary backtick code spans, not the CommonMark-style two-backtick delimiter. It works in some current clients but should be tested before relying on it.

**Source**

```text
``Use a `backtick` here``
```

**Expected result**

The inner single backticks appear as literal code characters.

> Client behaviour around unusual backtick runs can vary. A multiline code block is safer for complex examples.

---

# 10. Multiline code blocks

Use three backticks on their own opening and closing lines.

## 10.1 Plain multiline block

**Availability:** Portable Markdown + Discord

**Source**

~~~~text
```
Line one
Line two
Line three
```
~~~~

**Applied example**

```
Line one
Line two
Line three
```

---

## 10.2 Code block with language tag

**Availability:** Discord client-dependent syntax highlighting layered on a portable fenced code block

Put the language identifier immediately after the opening backticks.

**Source**

~~~~text
```json
{
  "enabled": true,
  "status": "ready"
}
```
~~~~

**Applied example**

```json
{
  "enabled": true,
  "status": "ready"
}
```

---

## 10.3 Markdown is disabled inside code blocks

**Availability:** Portable Markdown + Discord

**Source**

~~~~text
```
**Not bold**
||Not a spoiler||
# Not a header
<@123456789012345678> does not become a mention
```
~~~~

**Applied example**

```
**Not bold**
||Not a spoiler||
# Not a header
<@123456789012345678> does not become a mention
```

---

## 10.4 Showing triple backticks inside a Markdown document

**Availability:** Portable Markdown documentation technique; the inner triple fence is Discord syntax

When writing a `.md` guide such as this one, use a longer outer fence such as four tildes or four backticks.

**Source for a Markdown document**

````text
```json
{
  "example": true
}
```
````

> Discord itself expects triple-backtick fences. Tilde fences are useful in Markdown documents but are not the normal Discord code-block syntax.

---

# 11. Code-block language tags

The text after the opening backticks is a **language identifier** used for syntax highlighting.

````text
```LANGUAGE
code here
```
````

## Important compatibility note

Discord does **not** publish a single permanent, exhaustive, client-guaranteed list of every language tag.

- Unknown tags still normally produce a code block, but without useful highlighting.
- Aliases may differ across desktop, web, iOS, and Android.
- Discord’s highlighting implementation can change.
- Test unusual tags in Discord before relying on their colours.
- Use a canonical lowercase language name where possible.

The tables below are a **candidate identifier reference**, not a Discord support matrix. They include familiar names and aliases from common highlighting ecosystems; some are not canonical IDs in Discord's public Arborium runtime and may produce no highlighting.

For a dated implementation snapshot, Discord's public `@discord/arborium-rt` WASM package version `0.1.8` was released on 13 July 2026 with 100 bundled canonical grammar IDs. The Discord client may add aliases or special cases outside that package, and a bundled grammar does not prove that every client accepts the same code-fence tag.

## 11.1 Common client candidates

**Availability:** Discord client-dependent syntax highlighting; language identifiers are not Markdown semantics

| Purpose | Canonical ID in public Arborium 0.1.8 snapshot |
|---|---|
| No highlighting | Omit the tag |
| Markdown | `markdown` |
| Diff/patch | `diff` |
| JSON | `json` |
| YAML | `yaml` |
| TOML | `toml` |
| INI/config | `ini` |
| XML | `xml` |
| HTML | `html` |
| CSS | `css` |
| JavaScript | `javascript` |
| TypeScript | `typescript` |
| Python | `python` |
| Shell | `bash` |
| PowerShell | `powershell` |
| SQL | `sql` |

---

## 11.2 Web and data identifier candidates

**Availability:** Discord client-dependent syntax highlighting; language identifiers are not Markdown semantics

| Language/format | Candidate identifier(s) — not guaranteed |
|---|---|
| HTML | `html` |
| XML | `xml` |
| CSS | `css` |
| SCSS | `scss` |
| Sass | `sass` |
| Less | `less` |
| JavaScript | `js`, `javascript` |
| JSX | `jsx` |
| TypeScript | `ts`, `typescript` |
| TSX | `tsx` |
| JSON | `json` |
| JSON with comments | `jsonc` |
| YAML | `yaml`, `yml` |
| TOML | `toml` |
| GraphQL | `graphql` |
| SQL | `sql` |
| HTTP request/response | `http` |
| URI/URL | `uri` |
| Regular expressions | `regex` |
| Protocol Buffers | `protobuf`, `proto` |

### HTML example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```html
<section class="warning">
  <strong>Do not post here.</strong>
</section>
```
~~~~

**Applied example**

```html
<section class="warning">
  <strong>Do not post here.</strong>
</section>
```

### CSS example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```css
.warning {
  font-weight: bold;
  display: block;
}
```
~~~~

**Applied example**

```css
.warning {
  font-weight: bold;
  display: block;
}
```

### JavaScript example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```javascript
const status = "ready";
console.log(`Status: ${status}`);
```
~~~~

**Applied example**

```javascript
const status = "ready";
console.log(`Status: ${status}`);
```

### TypeScript example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```typescript
const status: "ready" | "pending" = "ready";
```
~~~~

**Applied example**

```typescript
const status: "ready" | "pending" = "ready";
```

---

## 11.3 Configuration and documentation identifier candidates

**Availability:** Discord client-dependent syntax highlighting; language identifiers are not Markdown semantics

| Language/format | Candidate identifier(s) — not guaranteed |
|---|---|
| Plain text | `text`, `txt`, `plaintext` |
| Markdown | `md`, `markdown` |
| JSON | `json` |
| JSONC | `jsonc` |
| YAML | `yaml`, `yml` |
| TOML | `toml` |
| INI | `ini` |
| Properties | `properties` |
| Nginx config | `nginx` |
| Apache config | `apache` |
| Dockerfile | `dockerfile`, `docker` |
| Makefile | `makefile`, `make` |
| CMake | `cmake` |
| LaTeX/TeX | `latex`, `tex` |

### Markdown example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```markdown
## Project Update

The task is **complete**.

-# Reference ID: `EXAMPLE-123`
```
~~~~

**Applied example**

```markdown
## Project Update

The task is **complete**.

-# Reference ID: `EXAMPLE-123`
```

### YAML example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```yaml
example_feature:
  enabled: true
  status: ready
```
~~~~

**Applied example**

```yaml
example_feature:
  enabled: true
  status: ready
```

### TOML example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```toml
[example]
enabled = true
status = "ready"
```
~~~~

**Applied example**

```toml
[example]
enabled = true
status = "ready"
```

### INI example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```ini
[example]
enabled=true
status=ready
```
~~~~

**Applied example**

```ini
[example]
enabled=true
status=ready
```

---

## 11.4 Shell and command-line identifier candidates

**Availability:** Discord client-dependent syntax highlighting; language identifiers are not Markdown semantics

| Language | Candidate identifier(s) — not guaranteed |
|---|---|
| POSIX shell | `sh`, `shell` |
| Bash | `bash` |
| Zsh | `zsh` |
| PowerShell | `powershell`, `ps1` |
| Windows batch | `bat`, `batch`, `cmd` |
| Fish shell | `fish` |
| Nushell | `nu`, `nushell` |

### Bash example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```bash
echo "Example feature enabled"
systemctl restart example-service
```
~~~~

**Applied example**

```bash
echo "Example feature enabled"
systemctl restart example-service
```

### PowerShell example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```powershell
$Status = "ready"
Write-Host "Status: $Status"
```
~~~~

**Applied example**

```powershell
$Status = "ready"
Write-Host "Status: $Status"
```

---

## 11.5 Programming-language identifier candidates

**Availability:** Discord client-dependent syntax highlighting; language identifiers are not Markdown semantics

| Language | Candidate identifier(s) — not guaranteed |
|---|---|
| C | `c` |
| C++ | `cpp`, `c++` |
| C# | `csharp`, `cs` |
| Java | `java` |
| Kotlin | `kotlin`, `kt` |
| Swift | `swift` |
| Objective-C | `objectivec`, `objc` |
| Go | `go`, `golang` |
| Rust | `rust`, `rs` |
| Python | `python`, `py` |
| Ruby | `ruby`, `rb` |
| PHP | `php` |
| Lua | `lua` |
| Perl | `perl`, `pl` |
| R | `r` |
| Dart | `dart` |
| Scala | `scala` |
| Groovy | `groovy` |
| Julia | `julia` |
| MATLAB | `matlab` |
| Visual Basic .NET | `vbnet`, `vb` |
| F# | `fsharp`, `fs` |
| OCaml | `ocaml` |
| Haskell | `haskell`, `hs` |
| Erlang | `erlang` |
| Elixir | `elixir`, `ex` |
| Clojure | `clojure`, `clj` |
| Lisp | `lisp` |
| Scheme | `scheme` |
| Prolog | `prolog` |
| Fortran | `fortran` |
| COBOL | `cobol` |
| Ada | `ada` |
| Pascal/Delphi | `pascal`, `delphi` |
| Nim | `nim` |
| Zig | `zig` |
| Crystal | `crystal` |
| V | `v` |
| Solidity | `solidity` |
| Move | `move` |
| WebAssembly text | `wasm`, `wat` |
| Assembly | `asm`, `assembly`, `x86asm` |

### Python example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```python
def update_status(item_id: int, status: str = "ready") -> None:
    print(f"{item_id}: {status}")
```
~~~~

**Applied example**

```python
def update_status(item_id: int, status: str = "ready") -> None:
    print(f"{item_id}: {status}")
```

### Rust example

**Availability:** Discord client-dependent syntax highlighting; the fenced code block itself is portable Markdown

**Source**

~~~~text
```rust
fn main() {
    let status = "ready";
    println!("Status: {status}");
}
```
~~~~

**Applied example**

```rust
fn main() {
    let status = "ready";
    println!("Status: {status}");
}
```

---

## 11.6 Build, automation, and infrastructure identifier candidates

**Availability:** Discord client-dependent syntax highlighting; language identifiers are not Markdown semantics

| Language/format | Candidate identifier(s) — not guaranteed |
|---|---|
| Dockerfile | `dockerfile`, `docker` |
| Makefile | `makefile`, `make` |
| CMake | `cmake` |
| Gradle | `gradle` |
| Terraform/HCL | `terraform`, `hcl` |
| Nix | `nix` |
| Git configuration | `gitconfig` |
| Git rebase | `git-rebase` |
| Diff/Patch | `diff`, `patch` |
| Nginx | `nginx` |
| Apache | `apache` |
| Ansible | `ansible`, `yaml` |
| Kubernetes manifests | `yaml` |
| GitHub Actions | `yaml` |

> These aliases are renderer-dependent. For infrastructure formats based on YAML, JSON, or shell, the base tag is often the most reliable choice.

---

## 11.7 Other specialised identifier candidates

**Availability:** Discord client-dependent syntax highlighting; language identifiers are not Markdown semantics

These may work on some current or legacy Discord clients but should be tested:

| Area | Tags worth trying |
|---|---|
| Brainfuck | `brainfuck` |
| Smalltalk | `smalltalk` |
| GDScript | `gdscript` |
| GLSL | `glsl` |
| HLSL | `hlsl` |
| ShaderLab | `shaderlab` |
| Verilog | `verilog` |
| SystemVerilog | `systemverilog` |
| VHDL | `vhdl` |
| LLVM IR | `llvm` |
| NASM | `nasm` |
| ARM assembly | `armasm` |
| RISC-V assembly | `riscv` |
| QML | `qml` |
| Vue | `vue` |
| Svelte | `svelte` |
| Handlebars | `handlebars`, `hbs` |
| Pug/Jade | `pug`, `jade` |
| Twig | `twig` |
| Jinja | `jinja`, `jinja2` |
| Liquid | `liquid` |
| Raku | `raku` |
| Apex | `apex` |
| ABAP | `abap` |
| D | `d` |
| ActionScript | `actionscript` |
| AppleScript | `applescript` |
| AutoHotkey | `autohotkey` |
| AutoIt | `autoit` |
| Awk | `awk` |
| Sed | `sed` |

---

# 12. Diff and ANSI colour blocks

## 12.1 Diff block

**Availability:** Discord client-dependent rendering; not portable Markdown colour semantics

A `diff` block highlights added and removed lines.

**Source**

~~~~text
```diff
- Example feature disabled
+ Example feature enabled
! Notice: configuration changed
```
~~~~

**Applied example**

```diff
- Example feature disabled
+ Example feature enabled
! Notice: configuration changed
```

> Exact colours and treatment of `!` vary by Discord client and highlighting engine. `+` and `-` are the most dependable diff markers.

---

## 12.2 ANSI coloured text — advanced Discord behaviour

**Availability:** Discord client-dependent rendering; not portable Markdown colour semantics

> **Client-observed and unsupported:** Discord's public Markdown and Developer documentation does not document ANSI code blocks, and `ansi` is not a canonical grammar in the public Arborium 0.1.8 bundle. Some desktop/web clients can interpret a limited set of ANSI escape sequences inside an `ansi` code block. Test before use; mobile and accessibility behaviour can differ.

**Structure**

~~~~text
```ansi
ESC[31mRed textESC[0m
```
~~~~

`ESC` above means the actual **escape control character** `U+001B`; typing the letters `E`, `S`, and `C` does not create the colour.

### Common ANSI style codes

| Code | Meaning |
|---:|---|
| `0` | Reset |
| `1` | Bold/intense |
| `4` | Underline |

### Foreground colour codes

| Code | Typical Discord colour |
|---:|---|
| `30` | Grey/dark |
| `31` | Red |
| `32` | Green |
| `33` | Yellow/gold |
| `34` | Blue |
| `35` | Pink/magenta |
| `36` | Cyan |
| `37` | White/light |

### Background colour codes

| Code | Typical Discord background |
|---:|---|
| `40` | Dark blue/black |
| `41` | Orange/red |
| `42` | Blue-grey |
| `43` | Grey-turquoise |
| `44` | Grey/blue |
| `45` | Indigo |
| `46` | Light grey/cyan |
| `47` | White/light |

### Combined ANSI sequence

Conceptual source:

```text
ESC[1;32mBold green success textESC[0m
```

> [!CAUTION]
> ANSI colours are not normal Markdown or a guaranteed Discord feature. They require invisible control characters, have a limited palette, and client support can differ—especially on mobile. Do not rely on colour alone to communicate important information.

---

# 13. Links and embed control

## 13.1 Raw URL

**Availability:** Portable URL text + Discord link handling

**Source**

```text
https://example.com
```

**Expected in Discord**

A clickable URL, potentially with a generated preview/embed.

---

## 13.2 Masked link

**Availability:** Portable Markdown + Discord

**Source**

```text
[Open the configuration guide](https://example.com/configuration)
```

**Applied example**

[Open the configuration guide](https://example.com/configuration)

> Discord may show a safety warning before opening a masked external link.

---

## 13.3 Formatting in link labels

**Availability:** Portable Markdown + Discord

**Source**

```text
[**Bold link label**](https://example.com)
```

**Applied example**

[**Bold link label**](https://example.com)

---

## 13.4 Suppress a single automatic link preview

**Availability:** Discord-specific link-preview behaviour

Wrap the URL in angle brackets.

**Source**

```text
<https://example.com>
```

**Expected in Discord**

A clickable URL without the normal rich preview/embed.

---

## 13.5 Spoilered link

**Availability:** Discord-only spoiler syntax applied to a URL

**Source**

```text
||https://example.com/secret||
```

**Expected in Discord**

The URL is covered by a spoiler until the viewer activates it. The exact interaction depends on the client and input method.

> Discord server-invite embeds may not be hidden the same way as ordinary links.

---

## 13.6 Links inside inline code are not clickable

**Availability:** Portable Markdown + Discord

**Source**

```text
`https://example.com`
```

**Applied example**

`https://example.com`

---

## 13.7 Markdown image syntax is not supported as an inline image

**Availability:** Markdown image syntax; not rendered as an inline image in Discord

**Source**

```text
![Alt text](https://example.com/image.png)
```

**Expected in Discord**

Do not rely on this rendering an inline Markdown image. Paste the raw image URL or upload the image instead.

---

## 13.8 Suppress embeds from an app, bot, or webhook

**Availability:** Discord API-only — message embed-suppression flag; not literal Markdown

For the user-facing text-syntax option, see section 13.4. Apps, bots, and webhooks can instead set the API message flag `SUPPRESS_EMBEDS` to suppress embeds on the message.

This is an API control, not text Markdown. Whether a sender can set or later change the flag depends on the endpoint and permissions.

---

# 14. Spoilers

## 14.1 Text spoiler

**Availability:** Discord-only spoiler syntax

**Source**

```text
The hidden value is ||example text||.
```

**Expected in Discord**

“The hidden value is” remains visible; “example text” is hidden until revealed.

---

## 14.2 Whole-message text spoiler

**Availability:** Discord-only spoiler syntax

**Source**

```text
||Everything in this section is hidden.||
```

**Expected in Discord**

The enclosed content is hidden behind a spoiler.

Discord's official client shortcut can also mark the following message as a spoiler:

```text
/spoiler The hidden message
```

The client applies spoiler formatting to the message. Treat `/spoiler` as a user-client shortcut, not as a bot/API message token.

---

## 14.3 Styled spoiler

**Availability:** Discord-only spoiler syntax

**Source**

```text
## ||Spoiler heading||

||**Bold secret information**||
```

The `##` remains at the beginning of the line so Discord can recognise the header. Spoiler the heading text and body separately; complex multi-line spoiler wrappers can be client-sensitive.

---

## 14.4 Spoilers do not work inside code

**Availability:** Discord-only spoiler syntax

**Source**

```text
`||This is literal code, not a spoiler.||`
```

**Applied example**

`||This is literal code, not a spoiler.||`

---

## 14.5 Attachment spoilers

**Availability:** Mixed Discord client + API — user upload controls and attachment/component spoiler fields

For uploaded images, videos, and files, use Discord’s **Mark as Spoiler** control before sending. This is a Discord UI feature, not ordinary text Markdown.

For bots and apps, the current Attachment object reports spoiler state through the `IS_SPOILER` flag:

**Attachment-object response excerpt**

```json
{
  "flags": 8
}
```

`8` is `1 << 3`. Treat this as returned attachment state; the current Create Message documentation does not promise that clients can set an arbitrary attachment `flags` value in an upload request.

For Components V2, a File component has a documented boolean field:

**File-component field excerpt**

```json
{
  "spoiler": true
}
```

> **Legacy/client-observed:** Traditional clients and many bot libraries also recognise the filename prefix below, but the current raw API reference does not document it as a Create Message field.

```text
SPOILER_
```

Example:

```text
SPOILER_secret-image.png
```

The official user-facing upload method is Discord's **Mark as Spoiler** control. For API uploads, follow the current endpoint or library documentation rather than assuming that a library's convenience option is a raw Discord API field.

---

# 15. Escaping Markdown

A backslash before a formatting character tells Discord to display that character literally.

## 15.1 Escape italics

**Availability:** Portable Markdown + Discord

**Source**

```text
\*This is surrounded by literal asterisks.\*
```

**Expected result**

`*This is surrounded by literal asterisks.*`

---

## 15.2 Escape underline/underscores

**Availability:** Discord-only escaping for Discord underline or spoiler markers

**Source**

```text
\_\_This is not underlined.\_\_
```

**Expected result**

`__This is not underlined.__`

---

## 15.3 Escape strikethrough

**Availability:** Markdown extension + Discord (GFM-style strikethrough; not CommonMark)

**Source**

```text
\~\~This is not crossed out.\~\~
```

**Expected result**

`~~This is not crossed out.~~`

---

## 15.4 Escape spoiler bars

**Availability:** Discord-only escaping for Discord underline or spoiler markers

**Source**

```text
\|\|This is not a spoiler.\|\|
```

**Expected result**

`||This is not a spoiler.||`

---

## 15.5 Escape a header

**Availability:** Portable Markdown + Discord

**Source**

```text
\# This is a literal hash, not a header.
```

**Expected result**

`# This is a literal hash, not a header.`

---

## 15.6 Escape a list marker

**Availability:** Portable Markdown + Discord

**Source**

```text
\- This is a literal hyphen.
1\. This is not an ordered-list item.
```

**Expected result**

`- This is a literal hyphen.`\
`1. This is not an ordered-list item.`

---

## 15.7 Escape a quote marker

**Availability:** Portable Markdown + Discord

**Source**

```text
\> This is not a quote.
```

**Expected result**

`> This is not a quote.`

---

## 15.8 Escape a backslash

**Availability:** Portable Markdown + Discord

**Source**

```text
\\
```

**Expected result**

A single visible backslash.

---

## 15.9 Prevent `@everyone` or `@here` from pinging

**Availability:** Discord-specific mention escaping and API caveat

**Source**

```text
\@everyone
\@here
```

**Expected result**

The text appears literally without triggering the special mention.

> Discord fixed backend handling for escaped `@everyone` and `@here` in 2026. Still verify bot/webhook mention controls separately, because bots can also govern pings through API-level allowed-mention settings.

---

## 15.10 Safest way to show complex literal Markdown

**Availability:** Portable Markdown + Discord

Use inline code or a code block.

**Source**

~~~~text
```
## This remains literal
**No bold**
||No spoiler||
<@123456789012345678> does not ping
```
~~~~

---

# 16. Discord mentions and entity markup

These are **Discord message tokens**, not standard Markdown. They are most useful in bot and webhook messages, though the Discord client normally inserts equivalent markup when you select a mention.

Enable **Developer Mode** in Discord when you need to copy IDs.

> [!WARNING]
> Valid user, role, and special mentions can notify people. Test with safe IDs and configure bot/webhook allowed-mention settings.

## 16.1 User mention

**Availability:** Discord-only message token

**Source**

```text
<@USER_ID>
```

**Example**

```text
<@123456789012345678>
```

**Expected in Discord**

With a valid user ID that Discord can resolve in the current context, a clickable user mention. Otherwise, Discord may leave the token unresolved or display it as plain text.

---

## 16.2 Deprecated user-mention form

**Availability:** Discord-only message token

**Source**

```text
<@!USER_ID>
```

Discord documents the exclamation-point form as deprecated. Prefer:

```text
<@USER_ID>
```

---

## 16.3 Channel mention

**Availability:** Discord-only message token

**Source**

```text
<#CHANNEL_ID>
```

**Example**

```text
<#123456789012345678>
```

**Expected in Discord**

With a valid channel ID accessible in the current context, a clickable channel reference normally displayed as the channel name. Otherwise, Discord may leave the token unresolved or display it as plain text.

---

## 16.4 Role mention

**Availability:** Discord-only message token

**Source**

```text
<@&ROLE_ID>
```

**Example**

```text
<@&123456789012345678>
```

**Expected in Discord**

A role mention. Whether it actually notifies members depends on permissions, role mentionability, and bot/API mention settings.

---

## 16.5 Special mentions

**Availability:** Discord-only message token

```text
@everyone
@here
```

- `@everyone` targets the server audience allowed to receive it.
- `@here` targets relevant currently online members.
- Actual delivery depends on permissions and each recipient’s notification settings.

Escape them when discussing the syntax literally:

```text
\@everyone
\@here
```

## 16.6 Bot and webhook mention controls

**Availability:** Discord API-only — `allowed_mentions` message control; not literal Markdown

For API-created messages, visible mention text and notification parsing are separate concerns controlled by `allowed_mentions`.

Current documented defaults are:

- Regular messages parse user, role, `@everyone`, and `@here` mentions.
- Interaction responses and webhooks parse user mentions only.

To suppress every mention notification while preserving visible mention text, include `allowed_mentions` in the message payload:

```json
{
  "content": "@everyone Example announcement",
  "allowed_mentions": {
    "parse": []
  }
}
```

You can also allow specific user or role IDs. Follow the current API schema: `parse` is mutually exclusive with explicit IDs for the same mention category.

---

# 17. Discord timestamps

Discord timestamps use Unix time in **whole seconds** and display in each viewer’s local timezone and locale.

## 17.1 Basic timestamp

**Availability:** Discord-only message token

**Source**

```text
<t:UNIX_TIMESTAMP>
```

**Example**

```text
<t:1618953630>
```

With no style, Discord uses the default date/time presentation.

---

## 17.2 Styled timestamp

**Availability:** Discord-only message token

**Source**

```text
<t:UNIX_TIMESTAMP:STYLE>
```

**Example**

```text
<t:1618953630:F>
```

---

## 17.3 All documented timestamp styles

**Availability:** Discord-only message token

| Style | Source example | Meaning |
|:---:|---|---|
| `t` | `<t:1618953630:t>` | Short time |
| `T` | `<t:1618953630:T>` | Time including seconds |
| `d` | `<t:1618953630:d>` | Short date |
| `D` | `<t:1618953630:D>` | Long date |
| `f` | `<t:1618953630:f>` | Long date with short time |
| `F` | `<t:1618953630:F>` | Full date with weekday and short time |
| `s` | `<t:1618953630:s>` | Short date and short time |
| `S` | `<t:1618953630:S>` | Short date and time with seconds |
| `R` | `<t:1618953630:R>` | Relative time, such as “5 minutes ago” |

> The exact order, wording, and 12/24-hour presentation depend on the viewer’s locale and Discord settings.

---

## 17.4 Useful timestamp message

**Availability:** Discord-only message token

**Source**

```text
The event starts <t:1893459600:F> — <t:1893459600:R>.
```

**Expected in Discord**

A full locally converted date/time followed by a relative value.

---

## 17.5 Unix seconds, not milliseconds

**Availability:** Discord-only message token

Correct conceptual value:

```text
1618953630
```

Incorrect JavaScript-style millisecond value:

```text
1618953630000
```

If your source produces milliseconds, divide by `1000` and use a whole integer.

---

# 18. Custom emoji markup

These are Discord-specific tokens.

## 18.1 Static custom emoji

**Availability:** Discord-only message token

**Source**

```text
<:NAME:EMOJI_ID>
```

**Example**

```text
<:example:123456789012345678>
```

**Expected in Discord**

The matching static custom emoji if the ID is valid and the emoji remains available to Discord.

For users, Nitro and the channel's **Use External Emoji** permission affect whether they can **send** an emoji from another server. Application-owned emoji follow Discord's current app-emoji rules. Rendering a valid token is a separate question from the sender's ability to insert it.

---

## 18.2 Animated custom emoji

**Availability:** Discord-only message token

**Source**

```text
<a:NAME:EMOJI_ID>
```

**Example**

```text
<a:example:123456789012345678>
```

**Expected in Discord**

The matching animated custom emoji if the ID is valid and the emoji remains available to Discord.

---

## 18.3 Unicode emoji

**Availability:** Portable Unicode text + Discord

Standard Unicode emoji require no markup:

```text
✨ 📌 ✅ ⚠️
```

Discord's current Developer reference says Desktop and Android use Twemoji, while iOS uses Apple's native emoji set, so appearance can differ by platform.

---

# 19. Slash-command mentions

A valid, accessible slash-command mention can render as a clickable command reference that populates the command in a user’s message box. Invalid or inaccessible IDs may remain unresolved.

These generally require the command’s actual application-command ID.

## 19.1 Top-level command

**Availability:** Discord-only message token

**Source**

```text
</COMMAND_NAME:COMMAND_ID>
```

**Example**

```text
</example:123456789012345678>
```

---

## 19.2 Command with subcommand

**Availability:** Discord-only message token

**Source**

```text
</COMMAND_NAME SUBCOMMAND:COMMAND_ID>
```

**Example**

```text
</example configure:123456789012345678>
```

---

## 19.3 Command with subcommand group

**Availability:** Discord-only message token

**Source**

```text
</COMMAND_NAME SUBCOMMAND_GROUP SUBCOMMAND:COMMAND_ID>
```

**Example**

```text
</example settings update:123456789012345678>
```

> These are Discord entity tokens—not ordinary links and not standard Markdown.

---

# 20. Guild-navigation links

Discord documents special guild-navigation tokens that link to areas of the **current server**.

## 20.1 Channels & Roles / onboarding customisation

**Availability:** Discord-only message token

```text
<id:customize>
```

---

## 20.2 Browse Channels

**Availability:** Discord-only message token

```text
<id:browse>
```

---

## 20.3 Server Guide

**Availability:** Discord-only message token

```text
<id:guide>
```

---

## 20.4 Linked Roles

**Availability:** Discord-only message token

```text
<id:linked-roles>
```

---

## 20.5 Specific linked role

**Availability:** Discord-only message token

```text
<id:linked-roles:ROLE_ID>
```

Example:

```text
<id:linked-roles:123456789012345678>
```

> Availability depends on the current server having the relevant feature configured.

---

# 21. Silent messages

> **Client-observed feature, not Markdown:** In current Discord clients, starting a user-composed message with `@silent` normally sends it with suppressed notification behaviour and may show a small bell indicator. Exact UI behaviour can vary by client. Discord does not list `@silent` in the Developer reference's message-formatting token table.

## 21.1 Basic silent message

**Availability:** Discord client-dependent feature; apps should use the documented API flag

**Source**

```text
@silent This message should not produce the normal notification sound.
```

`@silent` should be at the beginning of the message.

---

## 21.2 Silent mention

**Availability:** Discord client-dependent feature; apps should use the documented API flag

**Source**

```text
@silent <@123456789012345678> please check this when available.
```

**Expected in Discord**

In clients that support literal `@silent`, the mention remains visible while push and desktop notifications are normally suppressed. A notification badge can still appear.

> Bots and apps should use Discord's `SUPPRESS_NOTIFICATIONS` message flag rather than depending on literal `@silent` text. The current API documentation says the flag suppresses push and desktop notifications while leaving a notification badge.

---

# 22. Features not documented or not reliable in Discord

Discord is **not** a full CommonMark or GitHub Flavoured Markdown renderer. Discord does not publish an exhaustive negative-support matrix, so the table below means **do not rely on these features** in current Discord messages; it is not a permanent guarantee that no client will ever parse part of the syntax.

| Standard/extended Markdown feature | Current guidance |
|---|---|
| Header levels `####` through `######` | Not documented; use levels 1–3 only |
| Setext headers using `===` or `---` | Not documented; use `#` headings |
| Tables | Not documented; use a code block for alignment |
| Horizontal rules | Not documented; do not rely on them |
| Task lists such as `- [x]` | Not documented as interactive task lists |
| Footnotes and definition lists | Not documented |
| Heading IDs such as `{#custom-id}` | Not documented |
| Reference-style links | Not documented; use inline masked links |
| Inline Markdown images `![alt](url)` | Not documented; upload or paste the image URL |
| Raw HTML and `<br>` | Not rendered as general HTML |
| HTML comments | Do not rely on them being hidden |
| Superscript, subscript, or `==highlight==` | Not documented |
| Mermaid or math rendering | Not documented; fenced content remains code/text |
| Tilde-fenced or indented code blocks | Not documented; use backticks |
| GitHub alerts such as `[!NOTE]` | Not rendered as GitHub alert boxes |
| `<details>`, iframes, or embedded HTML video | Not supported as interactive HTML |

## 22.1 Table syntax remains plain text

**Availability:** Markdown feature not reliable in Discord

**Source**

```text
| Name | Status |
|---|---|
| Service | Ready |
```

Do not expect Discord to render this as a true table. Use a code block for aligned text instead:

~~~~text
```text
Name        Status
Client      Ready
Server      Pending
```
~~~~

---

## 22.2 Task lists are not interactive

**Availability:** Markdown feature not reliable in Discord

**Source**

```text
- [x] Enabled
- [ ] Reviewed
```

Discord may show this as ordinary list text, not clickable checkboxes.

---

## 22.3 Fourth-level headings are unsupported

**Availability:** Markdown feature not reliable in Discord

**Source**

```text
#### This is not a Discord header level
```

Use bold instead:

```text
**This is a bold section label**
```

---

# 23. Common formatting mistakes

## 23.1 Missing required space

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

Wrong:

```text
##Header
-#Subtext
>Quote
-List item
1.Item
```

Correct:

```text
## Header
-# Subtext
> Quote
- List item
1. Item
```

---

## 23.2 Not beginning at the start of a line

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

Headers, subtext, lists, and block quotes are line-oriented.

Wrong:

```text
Some text ## Header
Some text -# Subtext
```

Correct:

```text
## Header
-# Subtext
```

---

## 23.3 Unbalanced formatting markers

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

Wrong:

```text
**Bold text*
||Spoiler|
__Underline_
```

Correct:

```text
**Bold text**
||Spoiler||
__Underline__
```

---

## 23.4 Using an apostrophe instead of a backtick

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

Wrong character:

```text
'code'
```

Correct backtick:

```text
`code`
```

---

## 23.5 Language tag placed on the wrong line

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

Wrong:

~~~~text
```
json
{"enabled": true}
```
~~~~

Correct:

~~~~text
```json
{"enabled": true}
```
~~~~

---

## 23.6 Forgetting the closing code fence

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

Wrong:

~~~~text
```json
{"enabled": true}
~~~~

Correct:

~~~~text
```json
{"enabled": true}
```
~~~~

---

## 23.7 Expecting Markdown inside code blocks

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

This stays literal:

~~~~text
```
**not bold**
||not hidden||
```
~~~~

---

## 23.8 Expecting Discord-only syntax to preview in GitHub

**Availability:** Discord formatting guidance; availability depends on the syntax discussed

These may appear literal outside Discord:

```text
-# Discord subtext
||Discord spoiler||
<t:1618953630:R>
<@123456789012345678>
<:emoji:123456789012345678>
```

---

# 24. Full demonstration message

## 24.1 Template source — replace placeholders before pasting

**Availability:** Mixed portable Markdown and Discord-only tokens

~~~~text
## 📌 Project Update

<@123456789012345678> completed the **scheduled update** in <#123456789012345678>.

> **Summary:** The configuration was refreshed and is ready for review.

### Recommended next steps

1. Review the updated settings.
2. Run the **validation checks**.
3. Update the documentation.
4. Share the results with the team.

Review the [project guide](https://example.com/guide) for more information.

||Confirm the settings before publishing the changes.||

-# Reference ID: `EXAMPLE-123`
-# Updated: <t:1893459600:F> — <t:1893459600:R>
~~~~

## 24.2 Expected Discord structure

**Availability:** Mixed portable Markdown and Discord-only tokens

- A medium `##` header.
- A user mention and channel mention that become clickable when their IDs are valid and accessible in the current context.
- Bold status text.
- A block-quoted summary.
- A small `###` section header.
- A numbered list.
- A masked link.
- A hidden spoiler note.
- Two small/dim `-#` subtext lines.
- Dynamic local and relative timestamps.

---

# 25. Sources and maintenance notes

## Primary Discord sources

- [Discord Markdown Text 101](https://support.discord.com/hc/en-us/articles/210298617-Markdown-Text-101-Chat-Formatting-Bold-Italic-Underline)
- [Discord Developer Reference — Message Formatting](https://docs.discord.com/developers/reference#message-formatting)
- [Discord Developer Reference — Message Resource and allowed mentions](https://docs.discord.com/developers/resources/message)
- [Discord Developer Reference — Component Reference](https://docs.discord.com/developers/components/reference)
- [Discord Spoiler Tags](https://support.discord.com/hc/en-us/articles/360022320632-Spoiler-Tags)
- [Discord — Disable Automatic Link Embeds](https://support.discord.com/hc/en-us/articles/206342858--How-do-I-disable-auto-embed)
- [Discord’s Arborium syntax-highlighting runtime](https://github.com/discord/arborium-rt)
- [Arborium runtime 0.1.8 release](https://github.com/discord/arborium-rt/releases/tag/arborium-rt-wasm%400.1.8)
- [Discord Patch Notes — 6 March 2026](https://discord.com/blog/discord-patch-notes-march-6-2026)

## Secondary compatibility reference

- [Markdown Guide — Discord Support Matrix](https://www.markdownguide.org/tools/discord/)

## Maintenance warning

Discord can change its parser, editor, syntax-highlighting engine, aliases, and client behaviour without treating the Markdown subset as a fixed public standard.

When maintaining this document:

1. Trust current official Discord support and developer documentation first.
2. Test Discord-only syntax on desktop, web, iOS, and Android where cross-client consistency matters.
3. Treat unusual code-language aliases and ANSI colour rendering as best-effort features.
4. Avoid claiming that a language tag is permanently supported unless Discord publishes a stable client-facing list.
5. Keep important information understandable without colour, hover effects, or client-specific rendering.

---

# Compact copy/paste reference

**Availability:** Mixed — consult the per-section labels above for each feature

```text
*italic*
_italic_
**bold**
***bold italic***
__underline__
__*underline italic*__
__**underline bold**__
__***underline bold italic***__
~~strikethrough~~
||spoiler||

# Large header
## Medium header
### Small header
-# Subtext

- Bullet
* Bullet
1. Numbered item
  - Nested item

> Single-line quote
>>> Quote the rest of the message

`inline code`

[Masked link](https://example.com)
<https://example.com>

<@USER_ID>
<#CHANNEL_ID>
<@&ROLE_ID>
<t:UNIX_TIMESTAMP:F>
<:EMOJI_NAME:EMOJI_ID>
<a:EMOJI_NAME:EMOJI_ID>
</COMMAND_NAME:COMMAND_ID>
<id:TYPE>

@everyone
@here

/spoiler Hidden message

@silent Silent message
```

Multiline code-block structure:

~~~~text
```language
code
```
~~~~
