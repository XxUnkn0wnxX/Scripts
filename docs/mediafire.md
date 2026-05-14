# MediaFire.py

[`MediaFire.py`](../MediaFire.py) is a tiny interactive helper that combines the quickkey from one MediaFire link you control with the quickkey from a blocked MediaFire link you paste at runtime.

## What It Does

- reads a built-in MediaFire link from inside the script
- asks you to paste a blocked MediaFire link
- extracts both IDs
- prints a combined shareable MediaFire URL

## Important Setup

Before running it, edit the `Link1` value near the top of the script so it points to a MediaFire file link you own.

Example inside the script:

```python
Link1 = "https://www.mediafire.com/file/your-id/YourFile.zip/file"
```

## Basic Usage

Run the script:

```bash
python3 MediaFire.py
```

When prompted, paste the blocked MediaFire link:

```text
Enter Your Blocked Mediafire Link:
```

## Example

```bash
python3 MediaFire.py
```

Then paste:

```text
https://www.mediafire.com/file/example-id/BlockedFile.zip/file
```

The script prints:

```text
Your Link:
mediafire.com/?firstid,secondid
```

## Good To Know

- There are no CLI flags.
- If `Link1` is empty, the script exits immediately.
- If the pasted link is missing or invalid, the script exits with an error.
- Pressing `Ctrl+C` exits cleanly.
