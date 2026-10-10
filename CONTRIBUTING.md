# Contributing

## Development checks

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync --locked
PYTHONPATH=src uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Unit tests do not need network access or a Bun executable. Integration tests are
skipped when the bundled binary is absent. Licensing tests build real sdists and
wheels with a mocked download, check their metadata and notice bytes, and rebuild
a wheel from the sdist. Installed-wheel smoke tests also check the retained notices.

## Contribution licensing

Original contributions intentionally submitted for inclusion in this project are
under Apache-2.0, as described in section 5 of [LICENSE](LICENSE), unless explicitly
stated otherwise. Only submit material you have the right to contribute.

Add the existing SPDX copyright and Apache-2.0 identifiers to new original Python
files, using the actual copyright holder and year. Preserve notices and licensing
for third-party material; do not replace an upstream license with Apache-2.0.
Identify copied or adapted material and its source in the pull request so its
license compatibility and attribution requirements can be reviewed.

Do not edit standardized license terms. Keep attribution in `NOTICE` and
component-specific information in `THIRD_PARTY_NOTICES.md` and `LICENSES/`.

## Apache-2.0 transition

The Apache-2.0 transition applies to project-owned code in this branch and future
releases containing it. It does not revoke LGPL-2.1-or-later rights granted for
earlier releases and does not relicense Bun or its embedded dependencies.

Before releasing the transition, confirm that the copyright holder authorizes it
and that no copied code or independently owned contributions require additional
permission. Git authorship is useful evidence, not proof of copyright ownership.

## Bun updates and release checklist

The update bot only proposes version changes. Wheel builds deliberately reject a
Bun version that does not match `LICENSES/bun.json`, or notice files whose bytes
do not match that manifest. This is a **consistency check, not legal approval**.

Before publishing any release:

1. Resolve the outstanding redistribution review in `THIRD_PARTY_NOTICES.md`.
   Record the component inventory, required notices, applicable LGPL versions,
   and the selected corresponding-source/relinking distribution arrangements.
   Do not publish on the assumption that upstream binary availability proves
   compliance or transfers the distributor's responsibilities to upstream.
2. For a new Bun version, resolve its tag to an immutable source commit. Refresh
   `LICENSES/Bun-LICENSE.md` from that commit, preserving the upstream text (a
   final newline may be added). Keep release-specific source revisions and links
   in `LICENSES/bun.json`, not in the stable explanatory notices. Record
   SHA-256 hashes of the original upstream licensing document and each retained
   file, and collect any additional required component licenses and notices.
   Updating hashes alone does not constitute the review in step 1.
3. Keep dependency pins stable with `uv lock`; inspect the diff. For a
   packaging-only release, use an unused `.postN` version (for example,
   `1.4.2.post1`) rather than attempting to overwrite a published version.
   The build hook resolves that version to Bun `1.4.2`.
4. Run the development checks above, then build and inspect the artifacts:

   ```sh
   uv run --locked hatch build -t sdist
   uv run --locked hatch build -t wheel
   ```

   Check that both artifacts include `LICENSE`, `NOTICE`, third-party licensing
   information, and their `License-File` metadata. Confirm the sdist contains no
   Bun binary and that a wheel rebuilt from the sdist retains the same notices.
5. Require all platform builds and installed-wheel smoke tests to pass. Preserve
   the release-specific source/relinking materials and verify recipient access
   under the selected licensing provisions before tagging or publishing.

Automated checks cannot decide license compatibility, establish copyright
ownership, or certify that corresponding-source and relinking obligations have
been satisfied.
