import re
msg = message.decode("utf-8", errors="replace")
patterns = [
    r"(?im)^\s*Co-authored-by:.*(claude|anthropic).*\n?",
    r"(?im)^\s*🤖.*Generated with.*\n?",
    r"(?im)^\s*Generated with.*Claude.*\n?",
    r"(?im)^\s*Assisted-by:.*(claude|anthropic).*\n?",
]
for p in patterns:
    msg = re.sub(p, "", msg)
return msg.encode("utf-8")
