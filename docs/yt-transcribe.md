# yt-transcribe.py

[`yt-transcribe.py`](../python/yt-transcribe.py) downloads YouTube captions and saves them as plain text or DOCX. It is meant for quick transcript export without having to manually copy captions from the browser.

## What It Does

- accepts a YouTube URL or raw video ID
- downloads manual captions when available
- can prefer auto-generated captions
- cleans caption text for export
- can export plain text or `.docx`
- can keep or remove stage-direction tags like `[Music]`
- can trim output to one time point or a start/end range
- sanitizes output filenames automatically

## Basic Usage

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID'
```

Export as DOCX:

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID' --docx
```

Trim to a time range:

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID' --time '00:04:03 - 00:08:50'
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
      <td><nobr><code>url_or_id</code></nobr></td>
      <td>Positional</td>
      <td>Required. Accepts a normal YouTube URL or an 11-character video ID.</td>
    </tr>
    <tr>
      <td><nobr><code>--docx</code></nobr></td>
      <td>Flag</td>
      <td>Writes a DOCX file instead of plain text.</td>
    </tr>
    <tr>
      <td><nobr><code>--out &lt;path&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Sets the exact output file path instead of using automatic naming.</td>
    </tr>
    <tr>
      <td><nobr><code>--nostamp</code></nobr></td>
      <td>Flag</td>
      <td>Removes timestamps from the exported transcript.</td>
    </tr>
    <tr>
      <td><nobr><code>--gencaps</code></nobr></td>
      <td>Flag</td>
      <td>Prefers auto-generated captions over manual captions.</td>
    </tr>
    <tr>
      <td><nobr><code>--lang &lt;codes&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Comma-separated language preference list such as <code>en,en-US,en-GB</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--translate &lt;code&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Requests YouTube auto-translation into the given language code if available.</td>
    </tr>
    <tr>
      <td><nobr><code>--keep-tags</code></nobr></td>
      <td>Flag</td>
      <td>Keeps bracketed stage directions like <code>[Music]</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--no-yt-dlp</code></nobr></td>
      <td>Flag</td>
      <td>Skips the <code>yt-dlp</code> title lookup step.</td>
    </tr>
    <tr>
      <td><nobr><code>-v</code>, <code>--verbose</code></nobr></td>
      <td>Flag</td>
      <td>Enables verbose logging.</td>
    </tr>
    <tr>
      <td><nobr><code>--time &lt;time&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Stops at a single time or trims to a range like <code>00:04:03 - 00:08:50</code>.</td>
    </tr>
  </tbody>
</table>

## Quick Examples

Plain text export:

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID'
```

DOCX export with no timestamps:

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID' --docx --nostamp
```

Prefer generated captions and keep tags:

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID' --gencaps --keep-tags
```

Translate to Dutch:

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID' --translate nl
```

Write to a specific file:

```bash
python3 python/yt-transcribe.py 'https://www.youtube.com/watch?v=VIDEO_ID' --out transcript.txt
```

## Good To Know

- The script expects the repo-local `.venv` and `requirements.txt` to be set up.
- If a local `.venv` exists but you launch the script with the wrong Python, it re-execs itself into the repo-local environment.
- If the requested caption language is unavailable, the script falls back to what YouTube makes available.
