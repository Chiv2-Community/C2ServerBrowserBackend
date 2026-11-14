# Rust template provenance

These are repository-owned templates, not runtime patches of templates in the
generator JAR. Generation copies their bytes unchanged into its staging directory.

## Imported sources

Upstream: [OpenAPI Generator v7.17.0](https://github.com/OpenAPITools/openapi-generator/tree/v7.17.0/modules/openapi-generator/src/main/resources/rust).
License: [Apache-2.0](LICENSE.apache-2.0).

| Local template | Upstream path | Upstream SHA-256 |
| --- | --- | --- |
| `models/model-default.mustache` | `rust/model.mustache` | `5198867c46a267b82d6757eb1a3e81fd2b429974c3bf3b37bc108b14acb387af` |
| `reqwest/api.mustache` | `rust/reqwest/api.mustache` | `222f9a7155e8ac98f8e30dae943fa144142562311c8789962412a0f305aa4e75` |

Hashes identify the unmodified templates shipped in the pinned generator JAR.
The local copies contain intentional changes:

- Models: const/must-use constructors, `Self` return types, scoped import/argument
  lint allowances, Markdown type names, and conditional documentation comments.
- Operations: async-only JSON bodies and scalar parameters, error documentation,
  and an explicit `client/response` partial with status-directed error decoding.
  AWS signing, auth providers, multipart/forms and file streams are deliberately
  removed. `rust.py` rejects unsupported media, binary schemas, security schemes
  and parameter shapes before generation. Restore these capabilities explicitly
  when needed, including configuration, dependencies and tests.

Other files in this directory are project-owned templates. The generator still
provides unoverridden supporting templates; this is not a complete upstream fork.

## Updates

Edit local Mustache files directly. When upgrading the generator, review upstream
changes against the recorded versions, merge relevant changes explicitly, and
update these provenance records. Do not reintroduce Python string replacements,
marker slicing, or generated-source fixes.

Run generation drift checks, generator tests, and the full repository CI. Template
ownership-only changes should preserve generated SDK output byte-for-byte.
