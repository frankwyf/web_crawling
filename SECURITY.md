# Security Policy

## Supported Versions

Use the latest tagged release (currently v0.2.0). Earlier versions do not receive separate backports. Upgrade when a security fix is released.

## Reporting a Vulnerability

If you discover a security issue, please do not disclose it publicly in issues.

Use GitHub's **Security → Advisories → Report a vulnerability** when that option is available. If private reporting is unavailable, open an issue titled **Private security contact requested** with no vulnerability details or secrets; arrange a private channel with the maintainer before sending the report.

Include privately:

- A clear description of the vulnerability.
- Steps to reproduce.
- Potential impact.
- Suggested fix (optional).

This is a volunteer-maintained pre-1.0 project; response times are not guaranteed.

## Intended use and limits

Use trusted local indexes and crawl only authorized sites. Origin filtering checks responses after redirects and does not prevent outbound requests to redirected hosts. Do not treat it as an SSRF sandbox or pass untrusted start URLs to a privileged service. The local Flask development server has no authentication or tenant isolation and is not intended for public exposure. Automatic robots enforcement and resource limits remain roadmap items.

## Dependency checks

CI runs a strict pip-audit scan of installed dependencies and gates package/release jobs on its success. The local editable project is skipped because it is not a published PyPI distribution. A clean advisory scan means no known advisories were returned at that time, not that the project is free of vulnerabilities.

v0.2.0 updates Requests and Flask after checking the upstream [Requests netrc advisory](https://github.com/psf/requests/security/advisories/GHSA-9hjg-9r4m-mvj7), [Requests temporary-file advisory](https://github.com/psf/requests/security/advisories/GHSA-gc5v-m9x4-r6x2), and [Flask session-header advisory](https://github.com/pallets/flask/security/advisories/GHSA-68rp-wp8r-4726).
