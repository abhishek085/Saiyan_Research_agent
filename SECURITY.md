# Security Policy

## Supported Versions

This project is currently maintained as a local-first assistant. Security fixes should target the latest code on the default branch and the latest tagged release, if one exists.

| Version | Supported |
| --- | --- |
| Latest | Yes |
| Older snapshots | Best effort |

## Reporting a Vulnerability

Please do not post proof-of-concept exploits, secrets, or credential material in a public issue.

Use this process instead:

1. Contact the maintainer directly through a private channel you already trust.
2. Include reproduction steps, impact, affected files or configuration, and whether the issue requires local access, Discord access, Notion access, or Google access.
3. If you do not have a private contact path, open a minimal public issue requesting a secure disclosure channel without including exploit details.

The goal is to acknowledge the report quickly, reproduce it, ship a fix, and disclose the issue after users have time to rotate credentials or update.

## Scope

Security reports are especially helpful for issues involving:

- Credential leakage in local files, docs, or logs
- Discord bot token handling and channel permission boundaries
- Notion write scope escaping the configured root page
- Google OAuth token or client-secret exposure
- SSRF, prompt injection, or unsafe URL fetching through tool calls
- Container or host boundary mistakes in the Docker setup

## Local Deployment Guidance

This repository is designed to run with local secrets and local models. Before sharing the project publicly:

- Rotate any Discord, Notion, Google, or API credentials that have ever been committed, copied into screenshots, or pasted into docs.
- Keep `.env`, OAuth tokens, and client secrets out of version control.
- Limit Discord bot permissions to the minimum the assistant needs.
- Treat Notion and Google integrations as write-capable credentials and scope them narrowly.
- Rebuild and retest the container after security-sensitive changes so runtime behavior matches the checked-in code.

## Response Expectations

For valid reports, the intended response is:

1. Confirm receipt.
2. Assess severity and exposure.
3. Fix or mitigate.
4. Document any required credential rotation or user action.

If you fork this repository for your own deployment, update this file with your preferred contact channel before publishing.