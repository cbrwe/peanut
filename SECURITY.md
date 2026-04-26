# Security Policy

## Supported Versions

Peanut is in active early-stage development. Security fixes are applied to the latest released version only.

| Version | Supported |
| ------- | --------- |
| 1.x     | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in Peanut, please report it privately rather than opening a public GitHub issue.

**How to report:**

- Email cbrwe@proton.me with the subject line "Peanut security: [brief description]"
- Or use GitHub's private vulnerability reporting at https://github.com/cbrwe/peanut/security/advisories/new

**Please include:**

- A description of the vulnerability and its potential impact
- Steps to reproduce, or a proof-of-concept
- Your operating system and Peanut version
- Whether you are willing to be credited in the fix announcement

## What to expect

- I will acknowledge receipt within 7 days
- I will provide an initial assessment within 14 days
- Once a fix is ready, I will coordinate a release and credit you in the changelog (unless you prefer to remain anonymous)

## Scope

In scope:

- Vulnerabilities in the bundled Peanut application (macOS, Windows, Linux builds)
- Vulnerabilities in the Flask-based local server
- Issues that could allow unauthorized file access or data exfiltration

Out of scope:

- Issues in third-party dependencies (please report those upstream)
- Social engineering, phishing, or physical attacks
- Issues requiring physical access to an unlocked machine

Thank you for helping keep Peanut and its users safe.
