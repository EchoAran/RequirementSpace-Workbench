import re
try:
    import jieba
except ImportError:
    jieba = None

# Stop words to filter out
STOP_WORDS = {
    # Pronouns & basic verbs/particles
    "的", "了", "在", "是", "我", "你", "他", "她", "它", "们", "这", "那", "之", 
    "与", "和", "或", "并", "且", "因", "为", "所", "以", "但", "而", "及", "于", 
    "着", "也", "就", "都", "已经", "之后", "之前", "一个", "一些", "这个", "那个",
    "各种", "所有", "有", "无", "中", "个", "等", "及", "自", "至", "从", "往",
    "去", "到", "在", "用", "以", "把", "被", "让", "给", "对", "于", "向", "往",
    "到", "来", "去", "这", "那", "哪", "其", "己", "彼", "此", "这儿", "那儿",
    "什么", "谁", "哪里", "哪个", "如何", "怎么", "怎样", "多少", "几",
}

# Match punctuation and symbols
PUNCTUATION_RE = re.compile(r"[^\w\s\u4e00-\u9fff]")

def tokenize_for_search(text: str) -> list[str]:
    """
    Tokenize the input text for keyword searching.
    Normalizes text, splits Chinese text using jieba, extracts English/digits using regex,
    and filters out stop words, punctuation, and empty tokens.
    """
    if not text:
        return []

    # 1. Normalize text: lowercase
    normalized_text = text.lower()

    # 2. Extract English words, numbers, and technical identifiers (e.g. api_key, status-code)
    # Using regex to capture word segments containing letters, digits, underscores, and hyphens.
    eng_tokens = re.findall(r"[a-zA-Z0-9_\-]+", normalized_text)

    # Remove English/numbers to process Chinese text separately
    chinese_part = re.sub(r"[a-zA-Z0-9_\-]+", " ", normalized_text)
    # Remove punctuation
    chinese_part = PUNCTUATION_RE.sub(" ", chinese_part)

    # 3. Call jieba for search-oriented segmentation
    jieba_tokens = []
    if chinese_part.strip():
        if jieba is not None:
            # Using cut_for_search for search indexing
            jieba_tokens = list(jieba.cut_for_search(chinese_part.strip()))
        else:
            # Fallback: character and bigram tokens for Chinese text when jieba is not installed.
            jieba_tokens = []
            for seq in re.findall(r"[\u4e00-\u9fff]+", chinese_part):
                jieba_tokens.extend(seq[i:i + 2] for i in range(max(0, len(seq) - 1)))
                jieba_tokens.extend(char for char in seq)

    # Combine tokens
    combined_tokens = eng_tokens + jieba_tokens

    # 4. Clean tokens: strip whitespace, filter stop words, punctuation, and empty/single-char high-frequency words
    final_tokens = []
    for token in combined_tokens:
        token = token.strip()
        if not token:
            continue
        # Filter if it's a stop word
        if token in STOP_WORDS:
            continue
        # Filter single character punctuation
        if PUNCTUATION_RE.match(token):
            continue
        final_tokens.append(token)

    return list(dict.fromkeys(final_tokens))
