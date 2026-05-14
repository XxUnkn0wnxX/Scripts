# satisfactory_balancer.zsh

[`satisfactory_balancer.zsh`](../satisfactory_balancer.zsh) is a CLI helper for Satisfactory splitter and merger layouts. It mirrors the standard layouts from the official Satisfactory Balancer wiki and also supports Nico-style complex ratios.

## Reference Guides

- Official Satisfactory Balancer [wiki](https://satisfactory.wiki.gg/wiki/Balancer)
- NicoBuilds ratio [Guide](https://www.reddit.com/r/SatisfactoryGame/comments/1mitmza/guide_how_to_load_balance_weird_ratios_without/)

## What It Does

- plans classic `1:n` load balancers
- plans `n:m` belt balancers
- plans `n:m` belt compressors
- detects complex `1:A:B[:C...]` ratios using Nico-style math
- prints build steps you can follow in game

## Basic Usage

```bash
zsh satisfactory_balancer.zsh [options] n:m [n:m ...]
```

Simple example:

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

## Auto-Detected Modes

The script chooses the correct mode from the ratio shape automatically.

### LOAD-BALANCER

Used for:

- `1:n`

What it does:

- builds classic splitter trees
- rounds non-clean sizes up to the next clean split where needed
- reports loop-back lanes when a perfect clean split is not possible

Example:

```bash
zsh satisfactory_balancer.zsh 1:48
```

Meaning:

- `1:48` gives you a LOAD-BALANCER blueprint for a clean `1 -> 48` split

### BELT-BALANCER

Used for:

- `n:m` where `n > 1` and `m >= n`

What it does:

- describes split stages per input
- describes merge stages per output
- reports loop-back and padding information when needed

Example:

```bash
zsh satisfactory_balancer.zsh 4:7
```

Meaning:

- `4:7` gives you a BELT-BALANCER plan showing split layers, merge layers, lane budgets, and loop-back counts

### BELT-COMPRESSOR

Used for:

- `n:m` where `n > 1` and `m < n`

What it does:

- builds pack-first merger stacks
- shows explicit lane budgets
- shows priority-chain behavior such as `O1 -> O2`

Example:

```bash
zsh satisfactory_balancer.zsh 5:2
```

Meaning:

- `5:2` gives you a BELT-COMPRESSOR plan with pack-first priority notes like `O1 -> O2`

### NICO

Used for:

- `1:A:B`
- `1:A:B:C`

What it does:

- auto-detects complex multi-output ratios
- reuses the clean `1 -> N` planner internally
- prints a lane allocation table in the NicoBuilds style

Example:

```bash
zsh satisfactory_balancer.zsh 1:44:8
```

Meaning:

- `1:44:8` gives you a Nico-style split that divides `54` clean lanes into `44:8` plus loop-back

## Quick Examples

```bash
zsh satisfactory_balancer.zsh 1:48
zsh satisfactory_balancer.zsh 4:7
zsh satisfactory_balancer.zsh 5:2
zsh satisfactory_balancer.zsh 1:44:8
```

What those do:

- `1:48` -> LOAD-BALANCER
- `4:7` -> BELT-BALANCER
- `5:2` -> BELT-COMPRESSOR
- `1:44:8` -> NICO complex ratio mode

## Output Notes

The script does more than just print a ratio label.

It also prints build-oriented breakdowns such as:

- exact splitter counts per layer
- exact merger counts per layer
- lane budgets
- loop-back counts
- padding details where needed
- branch-sequence summaries

The recipe output is meant to be practical in game. For example, it can tell you things like:

```text
place 6 splitters to create 18 outputs
```

That is the main reason the old README section was detailed: the script is trying to tell you the actual build steps, not just the final math.

## Good To Know

- Bare numbers like `44` are invalid. Use `1:44`.
- Ratios must use positive integers only.
- The script auto-detects the proper mode from the ratio shape.
- You can pass more than one ratio in one command.
- Only `-h` or `--help` is supported as a flag.
