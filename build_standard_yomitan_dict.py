#!/usr/bin/env python3

import argparse
import copy
import html
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw" / "mefat.review"
STYLE_FILE = ROOT / "bunkei_yomitan_styles.css"
TERM_LIMIT = 2000
DEFAULT_DICT_NAME = "日本語文型辞典"
DEFAULT_OUTPUT = "Nihongo-Bunkei-Jiten.zip"
DEFAULT_AUTHOR = "HuangAntimony"
DEFAULT_PROJECT_URL = "https://github.com/HuangAntimony/Nihongo-Bunkei-Jiten"
DEFAULT_SOURCE_URL = "https://www.mefat.review/bunkei.ziten.html"
DEFAULT_INDEX_URL = f"{DEFAULT_PROJECT_URL}/releases/latest/download/index.json"
DEFAULT_DOWNLOAD_URL = f"{DEFAULT_PROJECT_URL}/releases/latest/download/Nihongo-Bunkei-Jiten.zip"
DEFAULT_REVISION = "0.0.0"

ENTRY_STYLE = {
    "padding": "0.1em 0",
    "margin": "0.2em 0",
}
META_STYLE = {
    "padding": "0",
    "marginBottom": "0.8em",
}
META_LINE_STYLE = {"margin": "0.12em 0"}
META_LABEL_STYLE = {"fontWeight": "bold", "color": "var(--text-color)"}
PREFACE_STYLE = {
    "padding": "0",
    "margin": "0.2em 0 0.95em 0",
}
SENSE_LIST_STYLE = {"margin": "0.55em 0 0 1.45em", "padding": "0"}
SENSE_ITEM_STYLE = {
    "padding": "0",
    "margin": "0 0 1em 0",
}
SENSE_TITLE_STYLE = {
    "padding": "0.05em 0.25em",
    "marginBottom": "0.45em",
    "fontWeight": "bold",
    "color": "var(--text-color)",
}
SUBSENSE_STYLE = {
    "padding": "0 0 0 0.75em",
    "margin": "0.7em 0 0.85em 0",
}
SUBSENSE_TITLE_STYLE = {
    "padding": "0",
    "marginBottom": "0.4em",
    "fontWeight": "bold",
    "color": "var(--text-color)",
}
PATTERN_LIST_STYLE = {"listStyleType": "none", "margin": "0.25em 0 0.6em 0", "padding": "0"}
PATTERN_ITEM_STYLE = {
    "padding": "0 0 0 0.6em",
    "margin": "0 0 0.35em 0",
    "color": "var(--text-color)",
}
BLOCK_STYLE = {"margin": "0.48em 0 0.72em 0"}
BLOCK_HEADING_STYLE = {"marginBottom": "0.28em"}
BLOCK_LABEL_BASE_STYLE = {
    "fontWeight": "bold",
    "fontSize": "0.84em",
    "padding": "0",
}
BLOCK_BODY_BASE_STYLE = {"padding": "0.12em 0 0.12em 0.7em"}
EXAMPLE_LINE_STYLE = {"margin": "0.24em 0"}
EXAMPLE_HEADER_STYLE = {
    "fontWeight": "bold",
    "fontSize": "0.82em",
    "padding": "0",
    "color": "var(--text-color)",
}
REFERENCE_LINE_STYLE = {"margin": "0.12em 0"}
BLOCK_KIND_STYLE_MAP = {
    "explains": {
        "label": {"color": "var(--accent-color, var(--link-color))"},
        "body": {},
    },
    "examples": {
        "label": {"color": "var(--sidebar-button-danger-background-color-active, var(--accent-color))"},
        "body": {},
    },
    "keyword": {
        "label": {"color": "var(--tag-dictionary-background-color, var(--accent-color))"},
        "body": {},
    },
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_fragment(fragment: str) -> ET.Element:
    fragment = html.unescape(fragment)
    fragment = re.sub(r"<img\b([^<>]*?)(?<!/)>", r"<img\1 />", fragment)
    fragment = re.sub(r"<br\b([^<>]*?)(?<!/)>", r"<br\1 />", fragment)
    return ET.fromstring(f"<root>{fragment}</root>")


def to_half_width(text: str) -> str:
    return "".join(
        chr(ord(ch) - 0xFEE0) if "！" <= ch <= "～" else ch
        for ch in text
    )


def normalize_text(text: str) -> str:
    text = text.replace("λ", "").replace("μ", "")
    text = text.replace("　", " ")
    text = text.replace("\r", "")
    text = text.replace("<", "＜").replace(">", "＞")
    text = re.sub(r"＜([^＞]+)＞", r"【\1】", text)
    text = text.replace("＜", "【").replace("＞", "】")
    text = re.sub(r"[（(][0-9０-９]+[)）](?=$|\n)", "", text)
    return text


def node_plain_text(node: ET.Element) -> str:
    parts = []
    if node is None:
        return ""
    if node.text:
        parts.append(node.text)
    for child in node:
        if child.tag != "rt":
            parts.append(node_plain_text(child))
        if child.tail:
            parts.append(child.tail)
    return re.sub(r"\s+", " ", normalize_text("".join(parts))).strip()


def merge_styles(*styles):
    merged = {}
    for style in styles:
        if style:
            merged.update(style)
    return merged or None


def normalize_data_key(key: str) -> str:
    # Yomitan prefixes dataset keys with `sc` during rendering.
    # Keys like `sc-role` would become malformed dataset names and be dropped.
    if key.startswith("sc-"):
        key = key[3:]
    return key


def merge_data(role=None, extra_data=None):
    merged = {}
    if role:
        merged["role"] = role
    if extra_data:
        for key, value in extra_data.items():
            merged[normalize_data_key(key)] = value
    return merged or None


def make_div(content, role=None, style=None, extra_data=None):
    node = {"tag": "div", "content": content}
    data = merge_data(role, extra_data)
    if data:
        node["data"] = data
    if style:
        node["style"] = style
    return node


def make_span(content, role=None, style=None, extra_data=None):
    node = {"tag": "span", "content": content}
    data = merge_data(role, extra_data)
    if data:
        node["data"] = data
    if style:
        node["style"] = style
    return node


def make_list(tag, items, role=None, style=None, extra_data=None):
    node = {"tag": tag, "content": items}
    data = merge_data(role, extra_data)
    if data:
        node["data"] = data
    if style:
        node["style"] = style
    return node


def append_text_parts(target, text: str):
    if not text:
        return
    text = normalize_text(text)
    if not text.strip():
        return
    segments = text.split("\n")
    for index, segment in enumerate(segments):
        if segment.strip():
            target.append(segment)
        if index < len(segments) - 1 and any(part.strip() for part in segments[index + 1 :]):
            target.append({"tag": "br"})


def convert_inline_children(node: ET.Element):
    parts = []
    append_text_parts(parts, node.text or "")
    for child in node:
        converted = convert_inline_node(child)
        if converted is not None:
            parts.append(converted)
        append_text_parts(parts, child.tail or "")
    return parts


def convert_inline_node(node: ET.Element):
    tag = node.tag
    if tag == "img":
        return None
    if tag == "br":
        return {"tag": "br"}
    if tag == "ruby":
        return {"tag": "ruby", "content": convert_inline_children(node)}
    if tag == "rt":
        return {"tag": "rt", "content": convert_inline_children(node)}
    if tag == "rp":
        return {"tag": "rp", "content": convert_inline_children(node)}
    if tag in {"span", "div"}:
        return convert_inline_children(node)
    return convert_inline_children(node)


def flatten_content(items):
    flat = []
    for item in items:
        if isinstance(item, list):
            flat.extend(flatten_content(item))
        else:
            flat.append(item)
    return flat


def has_visible_content(content) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(has_visible_content(item) for item in content)
    if isinstance(content, dict):
        if content.get("tag") == "br":
            return False
        return has_visible_content(content.get("content"))
    return False


def border_kind(text: str):
    if re.match(r"^[0-9０-９]+\s+", text):
        return "numbered"
    if re.match(r"^[A-Za-zａ-ｚＡ-Ｚ]\s+", text):
        return "lettered"
    return "pattern"


def strip_border_prefix(node: ET.Element, kind: str):
    if kind not in {"numbered", "lettered"}:
        return node

    node = copy.deepcopy(node)
    text_holder = node.find(".//span")
    if text_holder is None:
        text_holder = node

    original = text_holder.text or ""
    if kind == "numbered":
        text_holder.text = re.sub(r"^[0-9０-９]+\s+", "", original, count=1)
    else:
        text_holder.text = re.sub(r"^[A-Za-zａ-ｚＡ-Ｚ]\s+", "", original, count=1)
    return node


def extract_display_content(node: ET.Element):
    converted = convert_inline_children(node)
    return flatten_content(converted)


def clean_keyword(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).strip()


def clean_search_term(text: str) -> str:
    text = clean_keyword(text)
    return re.sub(r"\s*[0-9０-９]+$", "", text).strip()


def has_editorial_numeric_suffix(text: str) -> bool:
    text = clean_keyword(text)
    return bool(re.search(r"\s*[0-9０-９]+$", text))


def extract_heading_info(root: ET.Element):
    heading = root.find("div[@class='heading']")
    keyword = clean_keyword(node_plain_text(heading.find("span[@class='keyword']")))
    kanji_node = heading.find("span[@class='kanji']")
    kanji_plain = clean_keyword(node_plain_text(kanji_node)) if kanji_node is not None else ""
    kanji_display = extract_display_content(kanji_node) if kanji_node is not None else []
    return {
        "keyword": keyword,
        "keyword_search": clean_search_term(keyword),
        "kanji": kanji_plain,
        "kanji_display": kanji_display,
    }


def reading_from_keyword(text: str) -> str:
    text = to_half_width(clean_search_term(text))
    replacements = {
        "N": "えぬ",
        "V": "ぶい",
        "A": "えー",
        "R": "れんよう",
        "Q": "きゅー",
    }
    out = []
    for ch in text:
        if ch in replacements:
            out.append(replacements[ch])
            continue
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            out.append(chr(code - 0x60))
        else:
            out.append(ch)
    text = "".join(out)
    text = text.replace("Na", "な").replace("NA", "な")
    text = re.sub(r"[^ぁ-ゖー]", "", text)
    return text.replace("ー", "")


def make_block(kind: str, payload):
    return {"kind": kind, "payload": payload}


def parse_examples(node: ET.Element):
    sentences = node.findall(".//span[@class='sentence']")
    if not sentences:
        content = flatten_content(convert_inline_children(node))
        if not has_visible_content(content):
            return None
        return make_block("examples", [{"header": "", "content": content}])

    payload = []
    for sentence in sentences:
        header_node = sentence.find("span[@class='sentenceHeader']")
        content_node = sentence.find("span[@class='sentenceContent']")
        header = clean_keyword(node_plain_text(header_node))
        content = flatten_content(convert_inline_children(content_node))
        if not header and not has_visible_content(content):
            continue
        payload.append({"header": header, "content": content})
    if not payload:
        return None
    return make_block("examples", payload)


def parse_reference_content(text: str):
    content = []
    position = 0
    pattern = re.compile(r"【([^】]+)】")
    for match in pattern.finditer(text):
        if match.start() > position:
            content.append(text[position : match.start()])
        term = match.group(1)
        content.append({"tag": "a", "href": f"?query={term}&wildcards=off", "content": [term]})
        position = match.end()
    if position < len(text):
        content.append(text[position:])
    return flatten_content(content)


def parse_blocks(item_div: ET.Element):
    preface = {"patterns": [], "blocks": []}
    sections = []
    current_section = None
    current_subsense = None

    def current_target():
        if current_subsense is not None:
            return current_subsense
        if current_section is not None:
            return current_section
        return preface

    def new_section(title_content):
        return {"title": title_content, "patterns": [], "blocks": [], "subsenses": []}

    for child in list(item_div):
        class_name = child.attrib.get("class", "")

        if class_name == "border":
            plain = node_plain_text(child)
            kind = border_kind(plain)
            display_node = strip_border_prefix(child, kind)
            title_content = extract_display_content(display_node)

            if kind == "numbered":
                current_section = new_section(title_content)
                sections.append(current_section)
                current_subsense = None
            elif kind == "lettered":
                if current_section is None:
                    current_section = new_section([])
                    sections.append(current_section)
                current_subsense = new_section(title_content)
                current_section["subsenses"].append(current_subsense)
            else:
                current_target()["patterns"].append(title_content)

        elif class_name == "explains":
            plain = node_plain_text(child)
            if re.fullmatch(r"[(（][0-9０-９]+[)）]", plain):
                continue
            content = flatten_content(convert_inline_children(child))
            if has_visible_content(content):
                current_target()["blocks"].append(make_block("explains", content))

        elif class_name == "examples":
            examples_block = parse_examples(child)
            if examples_block is not None:
                current_target()["blocks"].append(examples_block)

        elif class_name == "keyword":
            plain = node_plain_text(child)
            content = parse_reference_content(plain)
            if has_visible_content(content):
                current_target()["blocks"].append(make_block("keyword", content))

    return preface, sections


def render_patterns(patterns):
    if not patterns:
        return None
    items = []
    for pattern in patterns:
        items.append(
            {
                "tag": "li",
                "data": {"role": "pattern-item"},
                "style": PATTERN_ITEM_STYLE,
                "content": pattern,
            }
        )
    return make_list("ul", items, role="pattern-list", style=PATTERN_LIST_STYLE)


def render_block(block):
    kind = block["kind"]
    theme = BLOCK_KIND_STYLE_MAP[kind]

    label_text = {
        "explains": "説明",
        "keyword": "参照",
        "examples": "例文",
    }[kind]
    label = make_div(
        [
            make_span(
                [label_text],
                role="block-label",
                style=merge_styles(BLOCK_LABEL_BASE_STYLE, theme["label"]),
                extra_data={"kind": kind},
            )
        ],
        role="block-heading",
        style=BLOCK_HEADING_STYLE,
        extra_data={"kind": kind},
    )

    if block["kind"] == "explains":
        return make_div(
            [
                label,
                make_div(
                    block["payload"],
                    role="block-body",
                    style=merge_styles(BLOCK_BODY_BASE_STYLE, theme["body"]),
                    extra_data={"kind": kind},
                ),
            ],
            role="block",
            style=BLOCK_STYLE,
            extra_data={"kind": kind},
        )

    if block["kind"] == "keyword":
        return make_div(
            [
                label,
                make_div(
                    [make_div(block["payload"], role="reference-line", style=REFERENCE_LINE_STYLE)],
                    role="block-body",
                    style=merge_styles(BLOCK_BODY_BASE_STYLE, theme["body"]),
                    extra_data={"kind": kind},
                ),
            ],
            role="block",
            style=BLOCK_STYLE,
            extra_data={"kind": kind},
        )

    lines = []
    for example in block["payload"]:
        line_content = []
        if example["header"]:
            line_content.append(
                make_span(
                    [example["header"]],
                    role="example-header",
                    style=EXAMPLE_HEADER_STYLE,
                )
            )
            line_content.append(" ")
        line_content.extend(example["content"])
        lines.append(make_div(line_content, role="example-line", style=EXAMPLE_LINE_STYLE))

    return make_div(
        [
            label,
            make_div(
                lines,
                role="block-body",
                style=merge_styles(BLOCK_BODY_BASE_STYLE, theme["body"]),
                extra_data={"kind": kind},
            ),
        ],
        role="block",
        style=BLOCK_STYLE,
        extra_data={"kind": kind},
    )


def render_sense_body(section):
    content = []
    patterns = render_patterns(section["patterns"])
    if patterns is not None:
        content.append(patterns)

    blocks = list(section["blocks"])
    if blocks and blocks[0]["kind"] == "examples":
        first_explain = next((i for i, block in enumerate(blocks) if block["kind"] == "explains"), None)
        if first_explain is not None:
            blocks.insert(0, blocks.pop(first_explain))

    for block in blocks:
        content.append(render_block(block))
    return content


def render_section(section):
    content = []

    if section["title"]:
        content.append(make_div(section["title"], role="sense-title", style=SENSE_TITLE_STYLE))

    content.extend(render_sense_body(section))

    for index, subsense in enumerate(section["subsenses"]):
        subsense_title = [f"{chr(ord('a') + index)}. "]
        subsense_title.extend(subsense["title"])
        subsense_content = [make_div(subsense_title, role="subsense-title", style=SUBSENSE_TITLE_STYLE)]
        subsense_content.extend(render_sense_body(subsense))
        content.append(make_div(subsense_content, role="subsense", style=SUBSENSE_STYLE))

    return {"tag": "li", "data": {"role": "sense-item"}, "style": SENSE_ITEM_STYLE, "content": content}


def build_glossary_content(entry_info, preface, sections):
    root_content = []

    meta_lines = []
    if entry_info["kanji"] and entry_info["kanji"] != entry_info["keyword_search"]:
        meta_lines.append(
            make_div(
                [
                    make_span(["表記: "], role="meta-label", style=META_LABEL_STYLE),
                    *entry_info["kanji_display"],
                ],
                role="meta-line",
                style=META_LINE_STYLE,
            )
        )
    if entry_info["keyword"] != entry_info["keyword_search"] and not has_editorial_numeric_suffix(entry_info["keyword"]):
        meta_lines.append(
            make_div(
                [
                    make_span(["索引: "], role="meta-label", style=META_LABEL_STYLE),
                    entry_info["keyword"],
                ],
                role="meta-line",
                style=META_LINE_STYLE,
            )
        )
    if meta_lines:
        root_content.append(make_div(meta_lines, role="meta", style=META_STYLE))

    if preface["patterns"] or preface["blocks"]:
        preface_content = [make_div(["基本情報"], role="sense-title", style=SENSE_TITLE_STYLE)]
        preface_content.extend(render_sense_body(preface))
        root_content.append(make_div(preface_content, role="preface", style=PREFACE_STYLE))

    if sections:
        root_content.append(
            make_list(
                "ol",
                [render_section(section) for section in sections],
                role="sense-list",
                style=SENSE_LIST_STYLE,
            )
        )

    return make_div(root_content, role="entry", style=ENTRY_STYLE)


def unique_entries(items):
    seen = set()
    output = []
    for item in items:
        key = (item["term"], item["reading"], item["sequence"], item["term_tags"])
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def build_entries():
    toc = read_json(RAW_DIR / "toc.json")
    dict_data = read_json(RAW_DIR / "dict.json")
    entries = []

    for sequence, toc_item in enumerate(toc, start=1):
        root = parse_fragment(dict_data[toc_item["id"]])
        entry_info = extract_heading_info(root)
        preface, sections = parse_blocks(root.find("div[@class='item']"))
        glossary = [{"type": "structured-content", "content": build_glossary_content(entry_info, preface, sections)}]
        reading = reading_from_keyword(entry_info["keyword"]) or entry_info["keyword_search"]

        primary_term = entry_info["keyword_search"] if has_editorial_numeric_suffix(entry_info["keyword"]) else entry_info["keyword"]
        primary_terms = [primary_term]
        cleaned_keyword = entry_info["keyword_search"]
        if cleaned_keyword and cleaned_keyword not in primary_terms:
            primary_terms.append(cleaned_keyword)
        if entry_info["kanji"] and entry_info["kanji"] not in primary_terms:
            primary_terms.append(entry_info["kanji"])

        for index, term in enumerate(primary_terms):
            entries.append(
                {
                    "term": term,
                    "reading": reading,
                    "definition_tags": "",
                    "rules": "",
                    "score": 10 if index == 0 else 1,
                    "glossary": glossary,
                    "sequence": sequence,
                    "term_tags": "grammar" if index == 0 else "grammar alias",
                }
            )

    return unique_entries(entries)


def build_index(
    dict_name: str,
    revision: str,
    author: str,
    project_url: str,
    source_url: str,
    index_url: str,
    download_url: str,
):
    return {
        "title": dict_name,
        "revision": revision,
        "format": 3,
        "sequenced": True,
        "author": author,
        "isUpdatable": True,
        "indexUrl": index_url,
        "downloadUrl": download_url,
        "url": project_url,
        "description": "Japanese grammar dictionary rebuilt from mefat.review with structured senses, examples, and visible furigana for Yomitan.",
        "attribution": f"Source data: {source_url}",
        "sourceLanguage": "ja",
        "targetLanguage": "ja",
    }


def build_tag_bank():
    return [
        ["grammar", "dictionary", 0, "日本語文型項目", 0],
        ["alias", "search", 0, "別表記・索引用の別名項目", 0],
    ]


def write_json(zip_file: zipfile.ZipFile, filename: str, payload):
    zip_file.writestr(filename, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def build_zip(
    output_path: Path,
    dict_name: str,
    revision: str,
    author: str,
    project_url: str,
    source_url: str,
    index_url: str,
    download_url: str,
):
    entries = build_entries()
    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zip_file:
        write_json(
            zip_file,
            "index.json",
            build_index(
                dict_name=dict_name,
                revision=revision,
                author=author,
                project_url=project_url,
                source_url=source_url,
                index_url=index_url,
                download_url=download_url,
            ),
        )
        write_json(zip_file, "tag_bank_1.json", build_tag_bank())
        zip_file.writestr("styles.css", STYLE_FILE.read_text(encoding="utf-8"))

        for offset in range(0, len(entries), TERM_LIMIT):
            bank_entries = entries[offset : offset + TERM_LIMIT]
            bank_payload = [
                [
                    entry["term"],
                    entry["reading"],
                    entry["definition_tags"],
                    entry["rules"],
                    entry["score"],
                    entry["glossary"],
                    entry["sequence"],
                    entry["term_tags"],
                ]
                for entry in bank_entries
            ]
            write_json(zip_file, f"term_bank_{offset // TERM_LIMIT + 1}.json", bank_payload)

    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Build a standard Yomitan dictionary from the mefat.review bunkei source data."
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output dictionary zip path",
    )
    parser.add_argument(
        "-n",
        "--name",
        default=DEFAULT_DICT_NAME,
        help="Dictionary title for index.json",
    )
    parser.add_argument(
        "-r",
        "--revision",
        default=DEFAULT_REVISION,
        help="Dictionary revision used by Yomitan update checks",
    )
    parser.add_argument(
        "--author",
        default=DEFAULT_AUTHOR,
        help="Dictionary author for index.json",
    )
    parser.add_argument(
        "--project-url",
        default=DEFAULT_PROJECT_URL,
        help="Project URL shown in dictionary details",
    )
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="Source data URL for attribution/reference",
    )
    parser.add_argument(
        "--index-url",
        default=DEFAULT_INDEX_URL,
        help="Latest index.json URL used by Yomitan update checks",
    )
    parser.add_argument(
        "--download-url",
        default=DEFAULT_DOWNLOAD_URL,
        help="Latest dictionary zip URL used by Yomitan update checks",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    entries = build_zip(
        output_path=output_path,
        dict_name=args.name,
        revision=args.revision,
        author=args.author,
        project_url=args.project_url,
        source_url=args.source_url,
        index_url=args.index_url,
        download_url=args.download_url,
    )
    print(f"Wrote {len(entries)} entries to {output_path}")


if __name__ == "__main__":
    main()
