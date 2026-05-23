# pyconvert.py

[`pyconvert.py`](../python/pyconvert.py) converts decimal and hex values between several binary-friendly formats. It is useful when checking save-file values, memory values, or other binary data.

## What It Does

- converts between decimal and hex
- supports half float, float, and double float
- supports unsigned integers from 8-bit to 64-bit
- can swap endianness
- supports little-endian mode
- enforces the valid bounds for the selected conversion type
- prints the converted value in the matching numeric form

## Basic Usage

Convert a float:

```bash
python3 python/pyconvert.py --float 3.14
```

Convert a 32-bit unsigned integer:

```bash
python3 python/pyconvert.py --uint32 4294967295
```

Swap endianness:

```bash
python3 python/pyconvert.py --swap 1234ABCD
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
      <td><nobr><code>value</code></nobr></td>
      <td>Positional</td>
      <td>Required input value to convert.</td>
    </tr>
    <tr>
      <td><nobr><code>--halffloat</code></nobr></td>
      <td>Flag</td>
      <td>Converts to or from half float.</td>
    </tr>
    <tr>
      <td><nobr><code>--float</code></nobr></td>
      <td>Flag</td>
      <td>Converts to or from 32-bit float.</td>
    </tr>
    <tr>
      <td><nobr><code>--doublefloat</code></nobr></td>
      <td>Flag</td>
      <td>Converts to or from 64-bit double float.</td>
    </tr>
    <tr>
      <td><nobr><code>--ubyte</code></nobr></td>
      <td>Flag</td>
      <td>Converts to or from unsigned byte.</td>
    </tr>
    <tr>
      <td><nobr><code>--ushort</code></nobr></td>
      <td>Flag</td>
      <td>Converts to or from unsigned short.</td>
    </tr>
    <tr>
      <td><nobr><code>--uint32</code></nobr></td>
      <td>Flag</td>
      <td>Converts to or from unsigned 32-bit integer.</td>
    </tr>
    <tr>
      <td><nobr><code>--uint64</code></nobr></td>
      <td>Flag</td>
      <td>Converts to or from unsigned 64-bit integer.</td>
    </tr>
    <tr>
      <td><nobr><code>--swap</code></nobr></td>
      <td>Flag</td>
      <td>Swaps endianness of the input value.</td>
    </tr>
    <tr>
      <td><nobr><code>--little</code></nobr></td>
      <td>Flag</td>
      <td>Uses little-endian byte order where supported.</td>
    </tr>
    <tr>
      <td><nobr><code>--debug</code></nobr></td>
      <td>Flag</td>
      <td>Enables debug output.</td>
    </tr>
  </tbody>
</table>

## Quick Examples

Half float:

```bash
python3 python/pyconvert.py --halffloat 3.5
```

Little-endian float:

```bash
python3 python/pyconvert.py --float --little 1.25
```

Unsigned short:

```bash
python3 python/pyconvert.py --ushort 65535
```

Endianness swap:

```bash
python3 python/pyconvert.py --swap DEADBEEF
```

## Good To Know

- You must choose one conversion mode.
- `--swap` is its own mode.
- `--little` changes byte order where that makes sense for the selected conversion.
