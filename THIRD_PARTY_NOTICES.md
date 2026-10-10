# Third-party licensing information

## Scope

`bun-wheel`'s original wrapper and tooling are Apache-2.0-licensed. Wheels also
contain an **unmodified upstream Bun executable**, which is a separate work
with its own licensing terms. Running it as a subprocess does not remove the
obligations associated with redistributing that executable.

`LicenseRef-Bun` in the distribution metadata refers to those upstream terms;
it is not a new license or permission to ignore them. `AND` records separate
applicable terms, not a choice between Apache-2.0 and Bun's licenses.

## Retained upstream information

- [LICENSES/bun.json](LICENSES/bun.json) is the single record of the bundled Bun
  version, immutable source links, WebKit and TinyCC revisions, and file checksums.
  These facts describe the tagged source configuration, not an independent
  attestation of every binary's build inputs.
- [LICENSES/Bun-LICENSE.md](LICENSES/Bun-LICENSE.md) retains the release-specific
  upstream licensing inventory and JavaScriptCore relinking instructions.
  Upstream bytes are preserved; a final newline may be added if needed.
- [LICENSES/MIT.txt](LICENSES/MIT.txt) retains Bun's MIT copyright and permission
  notice. [LICENSES/LGPL-2.1-or-later.txt](LICENSES/LGPL-2.1-or-later.txt) retains
  an LGPL text, not a claim about the license version of every embedded component.

Other embedded libraries and polyfills retain their respective upstream terms.
This document is stable across routine Bun updates; release-specific facts belong
in the manifest and snapshot above. New licensing requirements still require a
review and any necessary additional notices.

## Redistribution review still required

**The retained files are not a completed third-party compliance audit.** Before
publishing or redistributing wheels, the maintainer must resolve:

1. A complete component inventory for each shipped platform and the corresponding
   copyright notices, full license texts, and any required `NOTICE` content.
2. The exact applicable LGPL versions, corresponding source (including upstream
   modifications and build scripts), and the materials needed to modify and relink
   statically linked LGPL components using an applicable distribution option.
3. Availability and retention of those materials for recipients. A GitHub source
   link, a license copy, or an upstream build recipe alone is not a verified
   fulfillment of the applicable obligations.

No source-supply offer is made by this document. See the release checklist in
[CONTRIBUTING.md](CONTRIBUTING.md); automated refreshes do not replace that review.
