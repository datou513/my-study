"""Markdown 切块。

三条规则：
1. 标题建栈，块永远不跨节（换标题先 flush）。
2. 空行分段；段落是原子单位，按字数合并到 300–700 字。
3. 围栏代码块不切断，且和它前面的说明文字并成一块。

block 里只放正文，标题进 breadcrumb —— 重复存会让引用看起来啰嗦。
"""

import re
from dataclasses import dataclass

_SENT_END = "。！？；…!?;"
_SOFT_END = "，,、："
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

MIN_CHARS = 300
TARGET_CHARS = 500
MAX_CHARS = 700


@dataclass
class BlockDraft:  #切成块的文本
    seq: int
    breadcrumb: str
    heading: str | None
    text: str
    kind: str = "text"


def _find_cut(text: str, min_len: int, max_len: int) -> int:
    """在 [min_len, max_len] 里找切点：先句末，再逗号，都没有就硬切在 max_len。"""
    window = text[min_len:max_len]
    for marks in (_SENT_END, _SOFT_END):
        idx = max(window.rfind(ch) for ch in marks)
        if idx != -1:
            return min_len + idx + 1  # 切在标点之后
    return max_len


def _split_long(text: str, min_len: int = MIN_CHARS, max_len: int = MAX_CHARS) -> list[str]:
    """超长段落切成多段，优先切在句末标点。"""
    pieces: list[str] = []
    rest = text.strip()
    while len(rest) > max_len:
        cut = _find_cut(rest, min(min_len, len(rest) - 1), max_len)
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return pieces


def _parse_units(content: str) -> list[tuple[str, str, int]]:
    """第一遍：把 Markdown 行流拆成 (kind, text, level) 单元。

    kind: heading / para / code。代码块内的空行不当分隔符。
    """
    units: list[tuple[str, str, int]] = []
    para: list[str] = []
    code: list[str] = []
    in_code = False

    def flush_para() -> None:
        if para:
            units.append(("para", "\n".join(para).strip(), 0))
            para.clear()

    for line in content.splitlines():
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            if in_code:
                code.append(line)
                units.append(("code", "\n".join(code), 0))
                code = []
                in_code = False
            else:
                flush_para()
                in_code = True
                code = [line]
            continue

        if in_code:
            code.append(line)
            continue

        m = _HEADING_RE.match(line)
        if m:
            flush_para()
            units.append(("heading", m.group(2).strip(), len(m.group(1))))
            continue

        if not stripped:
            flush_para()
            continue

        para.append(line)

    flush_para()
    if code:  # 文档结尾没闭合的围栏，容错收下
        units.append(("code", "\n".join(code), 0))

    return units


def _merge_tiny(blocks: list[BlockDraft]) -> list[BlockDraft]:
    """尾块太短时并回上一块（同节、且总长不超 MAX），避免出现 9 个字的碎片块。"""
    out: list[BlockDraft] = []
    for b in blocks:
        if (
            out
            and len(b.text) < MIN_CHARS
            and out[-1].breadcrumb == b.breadcrumb
            and len(out[-1].text) + len(b.text) + 2 <= MAX_CHARS
        ):
            prev = out[-1]
            out[-1] = BlockDraft(
                seq=prev.seq,
                breadcrumb=prev.breadcrumb,
                heading=prev.heading,
                text=prev.text + "\n\n" + b.text,
                kind=prev.kind,
            )
        else:
            out.append(b)
    for i, b in enumerate(out, 1):
        b.seq = i
    return out


def split_markdown(content: str, doc_title: str) -> list[BlockDraft]:
    """把 Markdown 切成块。返回按顺序编号的 BlockDraft 列表。"""
    units = _parse_units(content)
    blocks: list[BlockDraft] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    buf_len = 0

    def breadcrumb() -> str:
        path = [title for _, title in stack]
        if not path or path[0] != doc_title:
            path = [doc_title, *path]  # H1 就是书名时不重复
        return " › ".join(path)

    def heading() -> str | None:
        return stack[-1][1] if stack else None

    def emit(text: str) -> None:
        blocks.append(
            BlockDraft(
                seq=len(blocks) + 1,
                breadcrumb=breadcrumb(),
                heading=heading(),
                text=text,
            )
        )

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            emit("\n\n".join(buf))
            buf = []
            buf_len = 0

    for kind, text, level in units:
        if kind == "heading":
            flush()  # 块不跨节
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            continue

        if kind == "code":
            if buf and buf_len + len(text) + 2 > MAX_CHARS:
                flush()
            if not buf and len(text) > MAX_CHARS:
                emit(text)  # 超长代码不切，宁可一块大
                continue
            buf.append(text)
            buf_len += len(text) + 2
            flush()  # 代码后收束：说明 + 代码自成一块
            continue

        # 普通段落
        if buf and buf_len + len(text) + 2 > MAX_CHARS:
            flush()

        if len(text) > MAX_CHARS:
            pieces = _split_long(text)
            for piece in pieces[:-1]:
                emit(piece)
            buf = [pieces[-1]]
            buf_len = len(pieces[-1])
        else:
            buf.append(text)
            buf_len += len(text) + 2

        if buf_len >= TARGET_CHARS:
            flush()

    flush()
    return _merge_tiny(blocks)


if __name__ == "__main__":  # 手工抽查切口：python -m src.ingest.markdown 文件.md
    import sys
    from pathlib import Path

    src = Path(sys.argv[1])
    for b in split_markdown(src.read_text(encoding="utf-8"), src.stem):
        head, tail = b.text[:20], b.text[-20:]
        print(f"[{b.seq}] {len(b.text):4d}字  {b.breadcrumb}\n     …{head} ▮ {tail}…")
