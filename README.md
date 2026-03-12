# ApiRegen

API reverse engineering toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Capture web traffic as HAR files, then let Claude analyze the endpoints, classify domains, detect auth patterns, and generate typed client code.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Install

```bash
claude plugin marketplace add livedge/apiregen
claude plugin install apiregen
```

Restart Claude Code. Done.

## Usage

Open Claude Code in any project directory and use the slash commands:

| Command | What it does |
|---------|-------------|
| `/capture` | Walks you through capturing web traffic as HAR files |
| `/recon` | Analyze captured traffic — domains, auth, protection, stack |
| `/mapping` | Cross-session differential analysis |
| `/report` | Full API intelligence report |
| `/schema` | Infer JSON schema from endpoints |
| `/typegen` | Generate typed classes (TypeScript, C#, Python, etc.) |
| `/investigate` | Ad-hoc deep-dive into specific endpoints |

### Typical workflow

1. `/capture` — capture traffic from target site (browser DevTools, Camoufox, or mitmproxy)
2. `/recon` — Claude analyzes the traffic and builds a context profile
3. `/report` — Claude writes a complete API intelligence report
4. `/typegen` — generate typed client code from discovered endpoints

## Standalone CLI (optional)

For use outside Claude Code:

```bash
# Install with CLI dependencies
uv tool install apiregen[cli]

# Guided interactive workflow
apiregen start

# Or individual commands
apiregen init myproject
apiregen capture -m browser -o myproject/captures/session1.har
apiregen recon myproject
```

Add browser capture support: `uv tool install apiregen[cli,browser]`

Add mitmproxy support: `uv tool install apiregen[cli,mitmproxy]`

## How it works

The plugin provides an MCP server (`apiregen-har`) with 16 tools for loading, searching, and analyzing HAR files. The slash commands give Claude structured prompts to use these tools for deep API analysis.

All intelligent analysis (domain classification, auth detection, protection identification) is done by Claude — the Python code only handles data parsing and querying.

## License

MIT
