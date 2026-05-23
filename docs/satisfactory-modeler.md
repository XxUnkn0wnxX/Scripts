# satisfactory-modeler.zsh

[`satisfactory-modeler.zsh`](../shell/satisfactory-modeler.zsh) is a macOS-only launcher and updater wrapper for [Satisfactory Modeler](https://satisfactorymodeler.itch.io/satisfactorymodeler). It keeps the unpacked app files in `shell/modeler/`, resolves a local Java JDK, and starts the app with sensible defaults.

## Platform

This wrapper is exclusively for macOS.

It depends on macOS-specific tools such as `/usr/libexec/java_home` and `ditto`, so it is not intended for Windows or Linux even though the upstream app publishes builds for those platforms.

## Requirements

### Required

- A Java JDK must be installed so `/usr/libexec/java_home` can resolve `JAVA_HOME`.
- You can install one with Oracle JDK: [oracle.com/anz/java/technologies/downloads](https://www.oracle.com/anz/java/technologies/downloads/)
- Or install one with the Homebrew Temurin cask: [formulae.brew.sh/cask/temurin](https://formulae.brew.sh/cask/temurin)
- Homebrew install page: [brew.sh](https://brew.sh/)

Example Homebrew install:

```bash
brew install --cask temurin
```

### Optional

- `7zz` or `7z` is optional.
- If `7zz` is installed, the script prefers it for ZIP extraction.
- If `7zz` is not installed but `7z` is available, it uses `7z`.
- If neither `7zz` nor `7z` is installed, the script falls back to macOS `ditto`, so the launcher still works without them.

Install the optional extractor with Homebrew:

```bash
brew install sevenzip
```

## What It Does

- keeps the unpacked app payload in a local `modeler/` subfolder beside the script
- downloads and refreshes the upstream app payload into that `modeler/` subfolder when needed
- resolves a Java JDK with `/usr/libexec/java_home`
- launches detached by default so you can close Terminal after starting it
- supports `--debug` mode so logs stay attached to the current terminal
- checks the upstream itch.io page for `satisfactory-modeler.zip` updates
- avoids re-downloading when the stored page timestamp, ETag, or ZIP hash has not changed
- can restore a missing `modeler.jar` from the cached ZIP before forcing a fresh download
- writes a PID file so the current process ID is easy to find later

## Setup

1. Install a Java JDK.
2. Run the wrapper with `zsh`.
3. Let the launcher populate `shell/modeler/` automatically on first run.

## Basic Usage

Normal launch:

```bash
zsh shell/satisfactory-modeler.zsh
```

Run attached with logs:

```bash
zsh shell/satisfactory-modeler.zsh --debug
```

Force a fresh update check first:

```bash
zsh shell/satisfactory-modeler.zsh --fupdate
```

## Arguments

<table>
  <thead>
    <tr>
      <th>Argument</th>
      <th>Type</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><nobr><code>--debug</code></nobr></td>
      <td>Flag</td>
      <td>Runs the app attached to the current terminal and keeps Java logs visible.</td>
    </tr>
    <tr>
      <td><nobr><code>--fupdate</code></nobr></td>
      <td>Flag</td>
      <td>Forces a fresh upstream update download and extraction before launch.</td>
    </tr>
    <tr>
      <td><nobr><code>--help</code>, <code>-h</code></nobr></td>
      <td>Flag</td>
      <td>Prints the built-in help page and exits.</td>
    </tr>
  </tbody>
</table>

## Environment Overrides

<table>
  <thead>
    <tr>
      <th>Variable</th>
      <th>Default</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><nobr><code>MODEL_CPU_LIMIT</code></nobr></td>
      <td><code>0</code></td>
      <td><code>0</code> means auto-detect physical CPU cores. Any value above <code>0</code> forces that CPU count for the JVM and the common ForkJoinPool.</td>
    </tr>
    <tr>
      <td><nobr><code>MODEL_HEAP_MIN</code></nobr></td>
      <td><code>4g</code></td>
      <td>Sets the JVM minimum heap size.</td>
    </tr>
    <tr>
      <td><nobr><code>MODEL_HEAP_MAX</code></nobr></td>
      <td><code>8g</code></td>
      <td>Sets the JVM maximum heap size.</td>
    </tr>
    <tr>
      <td><nobr><code>MODEL_JAVA_VERSION</code></nobr></td>
      <td><code>latest</code></td>
      <td>Uses the newest installed JDK by default, or an exact version such as <code>17</code> or <code>23</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>MODEL_UPDATE_TIMEOUT</code></nobr></td>
      <td><code>8</code></td>
      <td>Per-request timeout in seconds for the updater.</td>
    </tr>
    <tr>
      <td><nobr><code>MODEL_UPDATE_PAGE_URL</code></nobr></td>
      <td><code>satisfactorymodeler.itch.io/satisfactorymodeler</code></td>
      <td>Optional override for the upstream page URL.</td>
    </tr>
  </tbody>
</table>

## Quick Examples

Pin a specific Java version:

```bash
MODEL_JAVA_VERSION=17 zsh shell/satisfactory-modeler.zsh
```

Lower the memory cap:

```bash
MODEL_HEAP_MAX=4g zsh shell/satisfactory-modeler.zsh
```

Force four visible CPUs:

```bash
MODEL_CPU_LIMIT=4 zsh shell/satisfactory-modeler.zsh --debug
```

## Files It Creates

- `modeler/` for the unpacked app files such as `modeler.jar`, `game_data`, `images`, `languages`, and `libs`
- `modeler/updater/` for cached update files, cookies, and extraction work
- `modeler/.SMU_conf` for the stored updater state
- `modeler/modeler.pid` for the last-launched process ID

## Good To Know

- Detached mode sends stdout and stderr to `/dev/null`.
- Use `--debug` if you want to see Java output or confirm why a launch failed.
- If `modeler.jar` is missing, the script first tries to restore it from `modeler/updater/satisfactory-modeler.zip`.
- If the local cache cannot restore the JAR, the script forces a fresh updater download before launch.
