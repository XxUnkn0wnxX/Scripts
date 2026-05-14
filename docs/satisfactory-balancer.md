# satisfactory_balancer.zsh

[`satisfactory_balancer.zsh`](../satisfactory_balancer.zsh) is a CLI helper for Satisfactory splitter and merger layouts. You give it ratios and it tells you how to build the matching balancer layout.

## What It Does

- plans classic `1:n` load balancers
- plans `n:m` belt balancers
- plans `n:m` belt compressors
- detects complex `1:A:B[:C...]` ratios using Nico-style math

## Basic Usage

```bash
zsh satisfactory_balancer.zsh 1:48
```

Show help:

```bash
zsh satisfactory_balancer.zsh --help
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
      <td><nobr><code>n:m</code></nobr></td>
      <td>Positional</td>
      <td>One or more ratios. Inputs and outputs must be positive integers.</td>
    </tr>
    <tr>
      <td><nobr><code>-h</code>, <code>--help</code></nobr></td>
      <td>Flag</td>
      <td>Prints the built-in help and exits.</td>
    </tr>
  </tbody>
</table>

## Modes

### Load Balancer

Used for:

- `1:n`

Example:

```bash
zsh satisfactory_balancer.zsh 1:48
```

### Belt Balancer

Used for:

- `n:m` where `n > 1` and `m >= n`

Example:

```bash
zsh satisfactory_balancer.zsh 4:7
```

### Belt Compressor

Used for:

- `n:m` where `n > 1` and `m < n`

Example:

```bash
zsh satisfactory_balancer.zsh 5:2
```

### Complex Nico-style Ratios

Used for:

- `1:A:B`
- `1:A:B:C`

Example:

```bash
zsh satisfactory_balancer.zsh 1:44:8
```

## Good To Know

- Bare numbers like `44` are invalid. Use `1:44`.
- Ratios must use positive integers only.
- The script auto-detects the proper mode from the ratio shape.
- You can pass more than one ratio in one command.
