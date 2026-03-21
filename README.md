# Japanese Bunkei Dictionary for Yomitan

A rebuild of the Japanese grammar dictionary from mefat.review as a standard Yomitan dictionary.

Furigana is hidden by default because the source site's furigana appears to be third-party generated and may contain mistakes.

## Screenshots

![Light mode](screenshots/light.png)

![Dark mode](screenshots/dark.png)

## Build

Requirements:

- Python 3

Generate the dictionary locally:

```bash
python3 build_standard_yomitan_dict.py
```

Ellipsis headwords such as `お…ください` are maintained in
[`ellipsis_aliases.json`](ellipsis_aliases.json). This file can carry three
kinds of reviewable adjustments:

- `forms[]`: formal searchable headwords for the entry; the first item becomes
  the visible main headword
- `forms[].aliases`: concrete lookup forms extracted from ellipsis patterns; these
  generate redirect rows that point to the specific parent `form`, and alias
  items can be strings or `{term, reading}` objects when non-kana redirects need
  an explicit reading. When an alias can be matched uniquely against the
  reference term banks, its redirect row also inherits Yomitan `rules` so deinflection can still land
  on the redirect.

Once `forms` is present for an entry, it fully replaces the source-generated
headword set for that entry. Any original source form that is not listed there
will no longer be emitted as a searchable headword.

Example sentences and raw candidate fragments do not belong there. An empty
`aliases` array means no stable live alias has been confirmed for that form yet.

For entries without manual `forms`, the builder first prefers any explicit
source-site kanji headword it can already parse from the entry heading, so
source pairs such as `時 / とき` are emitted directly instead of keeping a
separate kana-only main row.

Conjugation-enabling `rules` are resolved from `raw/jitendex-yomitan/`. The
builder first tries exact term matches, then exact reading matches when they
resolve to a single non-empty Yomitan rule. Ambiguous or missing cases can be
filled manually in [`entry_rules_overrides.json`](entry_rules_overrides.json).

For source entries that are still kana-only after parsing, the builder also
checks the same Jitendex term banks for a unique non-kana `term + reading`
headword with the same reading (and, when available, the same Yomitan
`rules`). This canonicalization is only applied when Jitendex does not also
keep a kana headword for the same reading, so common kana-primary words such as
`する` stay kana-first while entries like `ずには居られない` align with
Jitendex.

By default, this writes:

```text
Nihongo-Bunkei-Jiten.zip
```

You can also set a custom output path and dictionary title:

```bash
python3 build_standard_yomitan_dict.py \
  --output custom-bunkei-dictionary.zip \
  --name "Japanese Bunkei Dictionary"
```

## Furigana Options

This dictionary hides furigana by default.

If you want to change that, copy either of these files into Yomitan's custom CSS(Popup CSS):

- [custom-css/furigana-always-visible.css](custom-css/furigana-always-visible.css): always show furigana
- [custom-css/furigana-on-hover.css](custom-css/furigana-on-hover.css): show furigana only on hover, overlaid above the text without changing line height

## Source Data

Thanks to the original source:

- [mefat.review bunkei.ziten](https://www.mefat.review/bunkei.ziten.html)

The raw files used to build this dictionary are cached in `raw/mefat.review/`.
