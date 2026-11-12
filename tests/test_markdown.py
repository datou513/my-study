import re

from src.ingest.markdown import MAX_CHARS, split_markdown

MD = """\
# 深度学习

## 第3章 注意力机制

### 3.2 自注意力

自注意力的核心是计算 Query、Key、Value 三个矩阵。

注意力机制让模型动态关注不同位置。

#### 3.2.1 位置编码

自注意力本身没有顺序信息，所以要额外注入位置编码。
"""


def _norm(s: str) -> str:
    """去掉空行和行首尾空白，用来比较"内容是否无损"。"""
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())


def test_heading_becomes_breadcrumb() -> None:
    blocks = split_markdown(MD, "深度学习")
    assert blocks
    assert blocks[0].breadcrumb == "深度学习 › 第3章 注意力机制 › 3.2 自注意力"
    assert blocks[0].heading == "3.2 自注意力"
    assert blocks[0].breadcrumb.count("深度学习") == 1  # H1 就是书名，不重复
    assert blocks[-1].breadcrumb.endswith("3.2.1 位置编码")


def test_long_paragraph_is_split() -> None:
    sentence = "这是用来测试切块逻辑的一句话，长度大概二十个字左右。"
    blocks = split_markdown("# 标题\n\n" + sentence * 100, "标题")
    assert len(blocks) >= 3
    assert all(len(b.text) <= MAX_CHARS for b in blocks)
    assert all(b.text.endswith(tuple("。！？")) for b in blocks)


def test_code_block_stays_with_context() -> None:
    md = (
        "# 笔记\n\n"
        "## 用法\n\n"
        "下面这段代码计算注意力权重。\n\n"
        "```python\n"
        "attn = softmax(Q @ K.T / math.sqrt(d)) @ V\n"
        "```\n"
    )
    blocks = split_markdown(md, "笔记")
    assert len(blocks) == 1
    assert "下面这段代码" in blocks[0].text
    assert "attn = softmax" in blocks[0].text


def test_short_paragraphs_merge() -> None:
    md = "# 笔记\n\n" + "\n\n".join(["这是一段很短的话。"] * 10)
    blocks = split_markdown(md, "笔记")
    assert len(blocks) == 1  # 十小段合并成一块，不是十条 bullet 式的碎片


def test_no_heading_falls_back_to_doc_title() -> None:
    blocks = split_markdown("就是一段没有标题的正文。", "我的笔记")
    assert blocks[0].breadcrumb == "我的笔记"
    assert blocks[0].heading is None


def test_lossless() -> None:
    """切块只搬位置、不改内容：去掉标题行后，拼回去必须和原文一致。"""
    body = re.sub(r"(?m)^#{1,6}\s+.*$", "", MD)
    expected = _norm(body)
    actual = _norm("\n".join(b.text for b in split_markdown(MD, "深度学习")))
    assert actual == expected
