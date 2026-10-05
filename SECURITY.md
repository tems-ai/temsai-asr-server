# Security policy

## Supported versions

Security fixes go into the latest release. Rebuild or pull the newest image
tag to get them. Official images are rebuilt with patched dependencies; images
you build yourself pick up fixes when you rebuild from the latest source.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| Older releases | No |

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report it privately, either way:

- GitHub: **Security → Report a vulnerability** on this repository
  ([private vulnerability reporting](https://github.com/tems-ai/temsai-asr-server/security/advisories/new)).
- Email: **support@tems.ai**, with "SECURITY" in the subject.

Please include the affected version or image tag, how to reproduce the issue
and its impact as you see it. We acknowledge reports within 3 working days,
keep you informed while we work on a fix, and credit you in the release notes
unless you prefer otherwise.

## Scope

In scope: the server code in this repository, the Dockerfile, the Helm chart
and manifests, and the official images at `ghcr.io/tems-ai/temsai-asr-server`.

Vulnerabilities in third-party components (NeMo, PyTorch, ffmpeg, the base
images) should also be reported upstream. Tell us as well if they affect the
official images, so we can ship a patched build.
