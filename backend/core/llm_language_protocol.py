CONTENT_LANGUAGE_PROTOCOL_MARKER = "[Content Language Protocol]"


def language_protocol(locale: str) -> str:
    if locale == "en-US":
        return (
            "[Content Language Protocol]\n"
            "You must output all user-visible natural language text, descriptions, titles, and values in English (en-US).\n"
            "Do NOT translate or modify any JSON keys, enum values, IDs, technical field names, or code snippets; keep them exactly as specified."
        )
    return (
        "[Content Language Protocol]\n"
        "你必须使用中文 (zh-CN) 输出所有用户可见的自然语言文本、描述、标题和内容值。\n"
        "请勿翻译或修改任何 JSON 键、枚举值、ID、技术字段名或代码片段，保持它们与规范指定的完全一致。"
    )


def remove_language_protocol(content: str) -> str:
    return content.split(CONTENT_LANGUAGE_PROTOCOL_MARKER, 1)[0].rstrip()


def append_language_protocol(prompt: str, locale: str) -> str:
    prompt = remove_language_protocol(prompt)
    protocol = language_protocol(locale)
    return f"{prompt}\n\n{protocol}" if prompt else protocol


def apply_language_protocol_to_messages(
    messages: list[dict],
    locale: str,
) -> list[dict]:
    protocol = language_protocol(locale)
    result = []
    for message in messages:
        next_message = dict(message)
        content = next_message.get("content")
        if isinstance(content, str):
            next_message["content"] = remove_language_protocol(content)
        result.append(next_message)

    for message in result:
        if message.get("role") == "system":
            content = message.get("content") or ""
            message["content"] = f"{content}\n\n{protocol}" if content else protocol
            return result

    result.insert(0, {"role": "system", "content": protocol})
    return result
