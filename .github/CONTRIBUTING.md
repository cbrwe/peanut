# Contributing to Peanut

Thanks for your interest. Peanut is open to contributions, and the easiest way to start is by opening an issue before you write code.

## Reporting bugs

Please use the bug report template. The most useful bug reports include:

1. Your OS and version (macOS 26, Windows 11, Ubuntu 24.04, etc.)
2. The Peanut version (Help -> About, or check the release tag)
3. What you did, what you expected, what actually happened
4. Any error messages from the console

For crashes, the log file is helpful:

- macOS: `~/Library/Application Support/Peanut/peanut.log`
- Windows: `%APPDATA%\Peanut\peanut.log`
- Linux: `~/.local/share/peanut/peanut.log`

## Suggesting features

Open an issue with the `enhancement` label. Describe the use case (what problem it solves for you) before the implementation idea.

## Pull requests

1. Fork the repo
2. Create a branch off `main`
3. Make your changes (please run the existing tests if you touch the scanner)
4. Open a PR with a clear description of what changed and why

Smaller PRs are easier to review and more likely to land.

## Development setup




## Building from source

See [BUILD.md](../BUILD.md) for cross-platform packaging instructions.

## Code style

Python: PEP 8 with 100-character line length. We don't enforce a formatter, but please run your changes through `black` or similar before submitting.

JavaScript/HTML/CSS: existing files use 2-space indentation, please match.

## Conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
