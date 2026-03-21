#!/usr/bin/env python3

import argparse
import copy
import html
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw" / "mefat.review"
STYLE_FILE = ROOT / "bunkei_yomitan_styles.css"
ELLIPSIS_ALIAS_FILE = ROOT / "ellipsis_aliases.json"
ENTRY_RULE_OVERRIDE_FILE = ROOT / "entry_rules_overrides.json"
JITENDEX_DIR = ROOT / "raw" / "jitendex-yomitan"
TERM_LIMIT = 2000
DEFAULT_DICT_NAME = "日本語文型辞典"
DEFAULT_OUTPUT = "Nihongo-Bunkei-Jiten.zip"
DEFAULT_AUTHOR = "HuangAntimony"
DEFAULT_PROJECT_URL = "https://github.com/HuangAntimony/Nihongo-Bunkei-Jiten"
DEFAULT_SOURCE_URL = "https://www.mefat.review/bunkei.ziten.html"
DEFAULT_INDEX_URL = f"{DEFAULT_PROJECT_URL}/releases/latest/download/index.json"
DEFAULT_DOWNLOAD_URL = f"{DEFAULT_PROJECT_URL}/releases/latest/download/Nihongo-Bunkei-Jiten.zip"
DEFAULT_REVISION = "0.0.0"
KANJI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

ENTRY_STYLE = {
    "padding": "0",
    "margin": "0",
}
META_STYLE = {
    "padding": "0",
    "marginBottom": "0.45em",
}
META_LINE_STYLE = {"margin": "0"}
META_LABEL_STYLE = {"fontWeight": "bold", "color": "var(--text-color)"}
PREFACE_STYLE = {
    "padding": "0",
    "margin": "0.15em 0 0.72em 0",
}
SENSE_LIST_STYLE = {"margin": "0.34em 0 0 1.45em", "padding": "0"}
SENSE_ITEM_STYLE = {
    "padding": "0",
    "margin": "0 0 0.76em 0",
}
SENSE_TITLE_STYLE = {
    "padding": "0",
    "marginBottom": "0.28em",
    "fontWeight": "bold",
    "color": "var(--text-color)",
}
SUBSENSE_STYLE = {
    "padding": "0 0 0 0.75em",
    "margin": "0.48em 0 0.65em 0",
}
SUBSENSE_TITLE_STYLE = {
    "padding": "0",
    "marginBottom": "0.24em",
    "fontWeight": "bold",
    "color": "var(--text-color)",
}
PATTERN_LIST_STYLE = {"listStyleType": "none", "margin": "0.18em 0 0.42em 0", "padding": "0"}
PATTERN_ITEM_STYLE = {
    "padding": "0 0 0 0.6em",
    "margin": "0 0 0.18em 0",
    "color": "var(--text-color)",
}
BLOCK_STYLE = {"margin": "0.32em 0 0.5em 0"}
BLOCK_HEADING_STYLE = {"marginBottom": "0.14em"}
BLOCK_LABEL_BASE_STYLE = {
    "fontWeight": "bold",
    "fontSize": "0.84em",
    "padding": "0",
}
BLOCK_BODY_BASE_STYLE = {"padding": "0.16em 0 0.16em 0.65em"}
EXAMPLE_LINE_STYLE = {"margin": "0.12em 0"}
EXAMPLE_HEADER_STYLE = {
    "fontWeight": "bold",
    "fontSize": "0.82em",
    "padding": "0",
    "color": "var(--text-color)",
}
REFERENCE_LINE_STYLE = {"margin": "0.06em 0"}
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


def build_internal_query_href(term: str, primary_reading: str = "") -> str:
    href = f"?query={quote(term, safe='')}&wildcards=off"
    if primary_reading:
        href += f"&primary_reading={quote(primary_reading, safe='')}"
    return href


def build_redirect_glossary(target_term: str, target_reading: str, source_term: str):
    return [
        {
            "type": "structured-content",
            "content": {
                "tag": "div",
                "lang": "ja",
                "data": {"content": "redirect-glossary"},
                "content": [
                    "⟶",
                    {
                        "tag": "a",
                        "href": build_internal_query_href(target_term, target_reading),
                        "lang": "ja",
                        "content": [target_term],
                    },
                ],
            },
        },
        [
            target_term,
            [f"redirected from {source_term}"],
        ],
    ]


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


def has_kanji(text: str) -> bool:
    return bool(KANJI_RE.search(clean_keyword(text)))


def load_ellipsis_entry_specs(path: Path):
    if not path.exists():
        return {}

    payload = read_json(path)
    if isinstance(payload, dict):
        payload = payload.get("entries", [])

    specs = {}
    for item in payload:
        entry_id = item["id"]
        specs[entry_id] = {"forms": list(item.get("forms", []))}
    return specs


def load_entry_rule_overrides(path: Path):
    if not path.exists():
        return {}

    payload = read_json(path)
    if isinstance(payload, dict):
        payload = payload.get("entries", [])

    overrides = {}
    for item in payload:
        entry_id = item["id"]
        rules = clean_keyword(item.get("rules", ""))
        if not rules:
            raise ValueError(f"Rule override for {entry_id} must define a non-empty rules string")
        overrides[entry_id] = rules
    return overrides


def find_jitendex_dir():
    if JITENDEX_DIR.exists():
        return JITENDEX_DIR
    return None


def build_reference_rule_index(reference_dir: Path | None):
    index = {"terms": {}, "readings": {}}
    if reference_dir is None:
        return index

    for bank_path in sorted(reference_dir.glob("term_bank_*.json")):
        for row in read_json(bank_path):
            term = clean_keyword(row[0])
            reading = clean_keyword(row[1])
            definition_tags = clean_keyword(row[2])
            rules = clean_keyword(row[3])
            if definition_tags == "forms" or not rules:
                continue
            index["terms"].setdefault(term, set()).add(rules)
            if reading:
                index["readings"].setdefault(reading, set()).add(rules)

    return index


def build_reference_headword_index(reference_dir: Path | None):
    index = {"reading_rules": {}, "readings": {}}
    if reference_dir is None:
        return index

    reading_rules_non_kana_candidates = {}
    reading_non_kana_candidates = {}
    reading_rules_has_kana = set()
    reading_has_kana = set()

    for bank_path in sorted(reference_dir.glob("term_bank_*.json")):
        for row in read_json(bank_path):
            term = clean_keyword(row[0])
            reading = clean_keyword(row[1])
            rules = clean_keyword(row[3])
            sequence = row[6]
            if not term or not reading or sequence <= 0:
                continue
            if term == reading or not has_kanji(term):
                reading_rules_has_kana.add((reading, rules))
                reading_has_kana.add(reading)
                continue
            reading_rules_non_kana_candidates.setdefault((reading, rules), set()).add(term)
            reading_non_kana_candidates.setdefault(reading, set()).add(term)

    for key, terms in reading_rules_non_kana_candidates.items():
        if len(terms) == 1 and key not in reading_rules_has_kana:
            index["reading_rules"][key] = next(iter(terms))

    for reading, terms in reading_non_kana_candidates.items():
        if len(terms) == 1 and reading not in reading_has_kana:
            index["readings"][reading] = next(iter(terms))

    return index


def resolve_reference_rules(terms, readings, rule_index):
    term_rules = set()
    for term in terms:
        term_rules.update(rule_index["terms"].get(term, set()))
    if len(term_rules) == 1:
        return next(iter(term_rules)), "reference-term"

    reading_rules = set()
    for reading in readings:
        if reading:
            reading_rules.update(rule_index["readings"].get(reading, set()))
    if not term_rules and len(reading_rules) == 1:
        return next(iter(reading_rules)), "reference-reading"

    return "", "none"


def resolve_entry_rules(entry_id: str, terms, readings, rule_index, rule_overrides):
    override_rules = rule_overrides.get(entry_id)
    if override_rules:
        return override_rules, "override"
    return resolve_reference_rules(terms, readings, rule_index)


def resolve_jitendex_headword_term(reading: str, rules: str, jitendex_headword_index):
    reading = clean_keyword(reading)
    if not reading:
        return ""
    if rules:
        term = jitendex_headword_index["reading_rules"].get((reading, clean_keyword(rules)))
        if term:
            return term
    return jitendex_headword_index["readings"].get(reading, "")


def canonicalize_primary_headword(headwords, rules: str, jitendex_headword_index):
    if not headwords:
        return headwords, False

    primary = headwords[0]
    reading = clean_keyword(primary["reading"] or primary["term"])
    primary_term = clean_keyword(primary["term"])
    if not reading or has_kanji(primary_term):
        return headwords, False

    preferred_term = resolve_jitendex_headword_term(reading, rules, jitendex_headword_index)
    if not preferred_term or preferred_term == primary_term:
        return headwords, False

    return [
        {
            "term": preferred_term,
            "reading": reading,
            "term_tags": "",
            "score": 10,
        }
    ], True


def build_source_headword_items(entry_info, entry_reading: str):
    primary_term = entry_info["keyword_search"] if has_editorial_numeric_suffix(entry_info["keyword"]) else entry_info["keyword"]
    terms = [primary_term]

    cleaned_keyword = entry_info["keyword_search"]
    if cleaned_keyword and cleaned_keyword not in terms:
        terms.append(cleaned_keyword)
    if entry_info["kanji"] and entry_info["kanji"] not in terms:
        terms.append(entry_info["kanji"])

    return [{"term": term, "reading": entry_reading} for term in terms]


def prefer_source_kanji_headwords(source_headwords):
    if not source_headwords:
        return source_headwords

    primary = source_headwords[0]
    primary_reading = clean_keyword(primary["reading"] or primary["term"])
    if not primary_reading:
        return source_headwords

    preferred = []
    seen = set()
    for item in source_headwords:
        term = clean_keyword(item["term"])
        reading = clean_keyword(item["reading"] or item["term"])
        if not term or not has_kanji(term) or reading != primary_reading:
            continue
        key = (term, reading)
        if key in seen:
            continue
        seen.add(key)
        preferred.append({"term": term, "reading": reading})

    return preferred or source_headwords


def build_entry_headword_items(source_headwords, form_specs):
    headwords = []
    seen = set()
    explicit_specs = []

    for spec in form_specs:
        term, reading = normalize_alias_item(spec)
        normalized = {
            "term": term,
            "reading": reading,
            "aliases": spec.get("aliases", []),
        }
        explicit_specs.append(normalized)

    def add(term: str, reading: str, term_tags: str, score: int):
        key = (term, reading)
        if key in seen:
            return
        seen.add(key)
        headwords.append(
            {
                "term": term,
                "reading": reading,
                "term_tags": term_tags,
                "score": score,
            }
        )

    if explicit_specs:
        first = explicit_specs[0]
        add(first["term"], first["reading"], "", 10)

        for item in explicit_specs[1:]:
            add(item["term"], item["reading"], "alias", 1)
        return headwords

    source_headwords = prefer_source_kanji_headwords(source_headwords)

    if source_headwords:
        first = source_headwords[0]
        add(first["term"], first["reading"], "", 10)

    for item in source_headwords:
        add(item["term"], item["reading"], "alias", 1)

    return headwords


def default_alias_reading(term: str) -> str:
    text = to_half_width(clean_keyword(term)).replace(" ", "")
    reading = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            reading.append(chr(code - 0x60))
        else:
            reading.append(ch)
    text = "".join(reading)
    if text and re.fullmatch(r"[ぁ-ゖー]+", text):
        return text.replace("ー", "")
    return ""


def normalize_alias_item(item):
    if isinstance(item, str):
        term = clean_keyword(item)
        reading = ""
    elif isinstance(item, dict):
        term = clean_keyword(item.get("term", ""))
        reading = clean_keyword(item.get("reading", ""))
    else:
        raise TypeError(f"Alias items must be strings or objects, got {type(item)!r}")

    if not term:
        raise ValueError("Alias term cannot be empty")
    return term, reading or default_alias_reading(term)


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


def build_ellipsis_alias_entries(
    entry_id: str,
    alias_forms,
    valid_source_terms,
    sequence: int,
    rule_index,
):
    alias_entries = []

    for form_spec in alias_forms:
        source_term = clean_keyword(form_spec["term"])
        if source_term not in valid_source_terms:
            raise ValueError(
                f"Alias form {source_term!r} for {entry_id} does not match any generated headword form"
            )
        redirect_target_term, redirect_target_reading = normalize_alias_item(form_spec)

        for alias_item in form_spec.get("aliases", []):
            term, reading = normalize_alias_item(alias_item)
            if term in valid_source_terms:
                continue
            alias_rules, _ = resolve_reference_rules([term], [reading], rule_index)
            alias_entries.append(
                {
                    "term": term,
                    "reading": reading,
                    "definition_tags": "",
                    "rules": alias_rules,
                    "score": -100,
                    "glossary": build_redirect_glossary(
                        redirect_target_term,
                        redirect_target_reading,
                        term,
                    ),
                    # Mirror the Jitendex/JMdict redirect convention: a negative sequence suppresses
                    # related-entry grouping while still leaving a stable link target.
                    "sequence": -sequence,
                    "term_tags": "",
                }
            )

    return alias_entries


def build_entries_with_stats():
    toc = read_json(RAW_DIR / "toc.json")
    dict_data = read_json(RAW_DIR / "dict.json")
    ellipsis_entry_specs = load_ellipsis_entry_specs(ELLIPSIS_ALIAS_FILE)
    rule_overrides = load_entry_rule_overrides(ENTRY_RULE_OVERRIDE_FILE)
    reference_dir = find_jitendex_dir()
    reference_rule_index = build_reference_rule_index(reference_dir)
    reference_headword_index = build_reference_headword_index(reference_dir)
    seen_ellipsis_spec_ids = set()
    seen_rule_override_ids = set()
    entries = []
    rule_stats = {"override": 0, "reference-term": 0, "reference-reading": 0, "none": 0}
    headword_stats = {"reference-canonicalized": 0}

    for sequence, toc_item in enumerate(toc, start=1):
        root = parse_fragment(dict_data[toc_item["id"]])
        entry_info = extract_heading_info(root)
        preface, sections = parse_blocks(root.find("div[@class='item']"))
        glossary = [{"type": "structured-content", "content": build_glossary_content(entry_info, preface, sections)}]
        reading = reading_from_keyword(entry_info["keyword"]) or entry_info["keyword_search"]
        source_headwords = build_source_headword_items(entry_info, reading)
        entry_spec = ellipsis_entry_specs.get(toc_item["id"])
        if entry_spec is not None:
            seen_ellipsis_spec_ids.add(toc_item["id"])
        form_specs = (entry_spec or {}).get("forms", [])
        headwords = build_entry_headword_items(source_headwords=source_headwords, form_specs=form_specs)
        headword_terms = [item["term"] for item in headwords]
        headword_readings = [item["reading"] for item in headwords if item["reading"]]

        rules, rule_source = resolve_entry_rules(
            entry_id=toc_item["id"],
            terms=headword_terms,
            readings=headword_readings,
            rule_index=reference_rule_index,
            rule_overrides=rule_overrides,
        )

        if not form_specs:
            headwords, canonicalized = canonicalize_primary_headword(headwords, rules, reference_headword_index)
            if canonicalized:
                headword_stats["reference-canonicalized"] += 1
                headword_terms = [item["term"] for item in headwords]
                headword_readings = [item["reading"] for item in headwords if item["reading"]]
                rules, rule_source = resolve_entry_rules(
                    entry_id=toc_item["id"],
                    terms=headword_terms,
                    readings=headword_readings,
                    rule_index=reference_rule_index,
                    rule_overrides=rule_overrides,
                )

        rule_stats[rule_source] += 1
        if rule_source == "override":
            seen_rule_override_ids.add(toc_item["id"])

        for item in headwords:
            entries.append(
                {
                    "term": item["term"],
                    "reading": item["reading"],
                    "definition_tags": "",
                    "rules": rules,
                    "score": item["score"],
                    "glossary": glossary,
                    "sequence": sequence,
                    "term_tags": item["term_tags"],
                }
            )

        alias_forms = form_specs
        if alias_forms:
            entries.extend(
                build_ellipsis_alias_entries(
                    entry_id=toc_item["id"],
                    alias_forms=alias_forms,
                    valid_source_terms={item["term"] for item in headwords},
                    sequence=sequence,
                    rule_index=reference_rule_index,
                )
            )

    unknown_alias_ids = sorted(set(ellipsis_entry_specs) - seen_ellipsis_spec_ids)
    if unknown_alias_ids:
        raise ValueError(f"Unknown ellipsis alias ids: {', '.join(unknown_alias_ids)}")

    unknown_rule_override_ids = sorted(set(rule_overrides) - seen_rule_override_ids)
    if unknown_rule_override_ids:
        raise ValueError(f"Unknown entry rule override ids: {', '.join(unknown_rule_override_ids)}")

    return unique_entries(entries), rule_stats, headword_stats


def build_entries():
    entries, _, _ = build_entries_with_stats()
    return entries


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
    entries, rule_stats, headword_stats = build_entries_with_stats()
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

    return entries, rule_stats, headword_stats


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
    entries, rule_stats, headword_stats = build_zip(
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
    matched_rule_entries = rule_stats["override"] + rule_stats["reference-term"] + rule_stats["reference-reading"]
    print(
        "Assigned Yomitan rules for "
        f"{matched_rule_entries} source entries "
        f"({rule_stats['reference-term']} exact-term, "
        f"{rule_stats['reference-reading']} reading-only, "
        f"{rule_stats['override']} manual overrides)"
    )
    print(
        "Canonicalized "
        f"{headword_stats['reference-canonicalized']} kana-only primary headwords "
        "to reference term+reading forms"
    )


if __name__ == "__main__":
    main()
