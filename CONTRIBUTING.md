# Contributing

Issues and pull requests are welcome. For anything larger than a small fix,
open an issue first so we can agree on the approach before you write the code.

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report
security problems privately, as described in [SECURITY.md](SECURITY.md), not
in a public issue.

## Where to start

- Issues labelled
  [`good first issue`](https://github.com/tems-ai/temsai-asr-server/labels/good%20first%20issue)
  are small and well scoped. Comment on one to say you are working on it.
- Issues labelled
  [`help wanted`](https://github.com/tems-ai/temsai-asr-server/labels/help%20wanted)
  are ones we would like help with.
- Documentation fixes, new client examples and test audio that shows a
  recognition problem are useful too, and need no prior discussion.

Help that is especially welcome: benchmarks on other hardware (add them to
[Sizing](README.md#sizing)), deployment recipes, and reports of how the
denoiser performs on your kind of noise.

## Pull requests

- Keep each pull request to one change, with tests for new behavior.
- Add a line under "Unreleased" in [CHANGELOG.md](CHANGELOG.md) if users will
  notice the change.
- Sign off every commit (`git commit -s`, see below).
- We aim to give a first review within a week. If you have heard nothing after
  that, a comment on the pull request is welcome.

## Development

See [Development](README.md#development) in the README for setup. Before you
open a pull request, run:

```bash
ruff check . && ruff format --check . && pytest
```

CI runs the same checks, plus Helm/manifest validation, hadolint and, for
changes to the image, a smoke test with the real model.

## Contribution terms

By submitting a contribution (a pull request, patch, or any other code,
documentation or configuration) to this repository, you agree to the
following terms.

### 1. License of your contribution

Your contribution is licensed under the [Apache License 2.0](LICENSE), the
same license as the rest of the source code, as set out in section 5 of that
license. You keep the copyright in your contribution.

### 2. Use in the Official Images

TemsSoft B.V. ("Tems.AI") builds the Official Images from this source code and
distributes them under the [Commercial License](COMMERCIAL-LICENSE.md). You
acknowledge that your contribution, once merged, may be included in the
Official Images and distributed, licensed and supported by Tems.AI under that
Commercial License or under any later version of it, as the Apache License 2.0
permits. You are not entitled to any payment, royalty or license fee for this.

This does not change the license of the source code: your contribution, like
the rest of the repository, stays available to everyone under the Apache
License 2.0.

### 3. Your right to contribute

You confirm that:

- the contribution is your original work, or you otherwise have the right to
  submit it under the Apache License 2.0;
- if you make the contribution as part of your job, your employer has allowed
  you to submit it under these terms, or does not claim rights in it;
- the contribution does not knowingly infringe any patent, copyright,
  trademark or other right of a third party;
- you have identified any third-party code, data or model weights it includes,
  with their license, and that license is compatible with the Apache License
  2.0. Do not add code under a copyleft license (for example GPL or AGPL) to
  this repository.

### 4. Sign-off (Developer Certificate of Origin)

Each commit must carry a `Signed-off-by` line certifying the
[Developer Certificate of Origin 1.1](https://developercertificate.org/):

```
Signed-off-by: Jane Doe <jane@example.com>
```

`git commit -s` adds it for you. Use your real name and an email address you
can be reached at. By signing off, you also confirm that you accept these
contribution terms.

### 5. Trademarks

Contributing does not grant you any right to use the "Tems.AI" name or logo,
as described in section 8 of the [Commercial License](COMMERCIAL-LICENSE.md).

### 6. No obligation

Tems.AI is not obliged to accept, merge, release or maintain any contribution.
Contributions are provided "AS IS", without warranties or conditions of any
kind, except as required by applicable law.

## Questions

For questions about these terms or about licensing, write to
**support@tems.ai**.
