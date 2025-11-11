# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.9.x   | :white_check_mark: |
| < 0.9   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in Hypomnemata, please report it to us privately. We take security issues seriously and appreciate your efforts to responsibly disclose your findings.

### How to Report

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, please email security reports to:

- **Email**: [Create a security advisory via GitHub](https://github.com/byrondenham/hypomnemata/security/advisories/new)

Alternatively, you can create a private security advisory directly on GitHub.

### What to Include

When reporting a vulnerability, please include:

1. **Description** of the vulnerability
2. **Steps to reproduce** the issue
3. **Potential impact** of the vulnerability
4. **Suggested fix** (if you have one)
5. **Version** of Hypomnemata affected
6. **Your contact information** for follow-up questions

### Response Timeline

- **Initial Response**: We aim to acknowledge receipt of your vulnerability report within 48 hours.
- **Status Updates**: We will send updates on the progress of fixing the vulnerability at least every 5 business days.
- **Resolution**: We aim to release a fix within 30 days of initial report, depending on complexity.
- **Disclosure**: We will coordinate with you on the disclosure timeline.

### Security Updates

Security updates will be released as patch versions (e.g., 0.9.1) and announced via:

- GitHub Security Advisories
- Release notes
- CHANGELOG.md

## Security Best Practices

When using Hypomnemata:

1. **Keep Updated**: Always use the latest version to benefit from security patches
2. **Validate Input**: Be cautious when importing notes from untrusted sources
3. **File Permissions**: Ensure your vault directory has appropriate file permissions
4. **Backup Regularly**: Maintain backups of your vault before running bulk operations
5. **Review Scripts**: If using the API or automation, review and validate scripts from untrusted sources

## Known Security Considerations

- **File System Access**: Hypomnemata operates on local files and requires appropriate file system permissions
- **SQLite Database**: The search index is stored in a SQLite database with no built-in encryption
- **No Authentication**: The optional API server (via `hypo serve`) has no built-in authentication - use appropriate network controls
- **No Telemetry**: Hypomnemata does not collect or send any telemetry or usage data

## Excluded Vulnerabilities

The following are generally **not** considered security vulnerabilities:

- Issues requiring physical access to the machine
- Issues in third-party dependencies (report to those projects directly)
- Issues in example/test code that is not part of the production package
- Social engineering attacks
- Denial of service from malformed markdown files (Hypomnemata is a single-user local tool)

## Security Features

- **No Remote Code Execution**: Hypomnemata does not execute arbitrary code from notes
- **Deterministic Builds**: Release artifacts include checksums for verification
- **Dependency Security**: We monitor dependencies for known vulnerabilities
- **Minimal Dependencies**: We keep the dependency tree small to reduce attack surface

## Thank You

We appreciate the security research community's efforts in helping keep Hypomnemata and its users safe. Responsible disclosure helps us ensure the security and privacy of all users.
