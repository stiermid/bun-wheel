# Third-party licensing information

## Scope

`bun-wheel`'s original wrapper and tooling are Apache-2.0-licensed. Wheels also
contain an **unmodified upstream Bun executable**, which is a separate work
with its own licensing terms. Running it as a subprocess does not remove the
obligations associated with redistributing that executable.

`LicenseRef-Bun` in the distribution metadata refers to those upstream terms;
it is not a new license or permission to ignore them. `AND` records separate
applicable terms, not a choice between Apache-2.0 and Bun's licenses.

## Retained information for Bun 1.4.2

- Bun source: [bun-v1.4.2](https://github.com/oven-sh/bun/tree/744846f844374847c902b5e7fd59b4342a51ef99).
- Binary assets and checksums: [upstream release](https://github.com/oven-sh/bun/releases/tag/bun-v1.4.2).
- Bun's MIT copyright and permission notice: [LICENSES/MIT.txt](LICENSES/MIT.txt).
- Upstream licensing inventory and JavaScriptCore relinking instructions:
  [LICENSES/Bun-LICENSE.md](LICENSES/Bun-LICENSE.md). The upstream content is
  preserved, with only a final newline added.
- A retained LGPL-2.1 text: [LICENSES/LGPL-2.1-or-later.txt](LICENSES/LGPL-2.1-or-later.txt).
  This does not establish the license version of every embedded LGPL component.
- Provenance and file checksums: [LICENSES/bun.json](LICENSES/bun.json).

Bun's release-pinned build scripts identify these LGPL-related source revisions:

| Component | Source revision | Bun build configuration |
|---|---|---|
| WebKit / JavaScriptCore | [`2e2aa2290fac856d6f451ceacb58f7f5b44dd057`](https://github.com/oven-sh/WebKit/tree/2e2aa2290fac856d6f451ceacb58f7f5b44dd057) | [`webkit.ts`](https://github.com/oven-sh/bun/blob/744846f844374847c902b5e7fd59b4342a51ef99/scripts/build/deps/webkit.ts) |
| TinyCC | [`05f0fafaa3be31e31d7b4b5c17dc60f62c991171`](https://github.com/oven-sh/tinycc/tree/05f0fafaa3be31e31d7b4b5c17dc60f62c991171) | [`tinycc.ts`](https://github.com/oven-sh/bun/blob/744846f844374847c902b5e7fd59b4342a51ef99/scripts/build/deps/tinycc.ts) |

These references describe the tagged source configuration. They are not an
independent attestation of the contents or build inputs of every release binary.
Other embedded libraries and polyfills retain the copyright, attribution, and
license requirements of their respective authors. The upstream inventory links
to them; it must not be treated as an exhaustive, release-specific notice bundle.

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

No source-supply offer is made by this document. Obtain qualified licensing
advice if the applicable distribution requirements are uncertain. The release
checklist in [CONTRIBUTING.md](CONTRIBUTING.md) records the required review steps.
