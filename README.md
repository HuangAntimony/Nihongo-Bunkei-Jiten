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
