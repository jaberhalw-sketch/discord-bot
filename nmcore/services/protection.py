import re
import time
from collections import defaultdict, deque
from nmcore.db import db


_message_times = defaultdict(deque)
_duplicate_messages = defaultdict(deque)


DEFAULTS = {
    "enabled": 1,
    "bad_words_enabled": 1,
    "links_enabled": 1,
    "spam_enabled": 1,
    "mass_mention_enabled": 1,
    "delete_messages": 1,
    "timeout_enabled": 0,
    "bad_words": "قحبه,قحبة,كس,كسمك,fuck,shit,bitch",
    "ignored_channels": "",
    "whitelist_roles": "",
    "spam_threshold": 6,
    "spam_window": 8,
    "mention_threshold": 6,
    "duplicate_enabled": 1,
    "duplicate_threshold": 4,
    "duplicate_window": 15,
    "invite_block_enabled": 1,
    "link_whitelist": "",
    "caps_enabled": 0,
    "caps_percent": 85,
    "caps_min_length": 18,
    "max_newlines_enabled": 0,
    "max_newlines": 12,
}


def ensure_schema():
    conn = db()
    cur = conn.cursor()

    columns = {
        "spam_threshold": "INTEGER DEFAULT 6",
        "spam_window": "INTEGER DEFAULT 8",
        "mention_threshold": "INTEGER DEFAULT 6",
        "duplicate_enabled": "INTEGER DEFAULT 1",
        "duplicate_threshold": "INTEGER DEFAULT 4",
        "duplicate_window": "INTEGER DEFAULT 15",
        "invite_block_enabled": "INTEGER DEFAULT 1",
        "link_whitelist": "TEXT DEFAULT ''",
        "caps_enabled": "INTEGER DEFAULT 0",
        "caps_percent": "INTEGER DEFAULT 85",
        "caps_min_length": "INTEGER DEFAULT 18",
        "max_newlines_enabled": "INTEGER DEFAULT 0",
        "max_newlines": "INTEGER DEFAULT 12",
    }

    for name, sql in columns.items():
        try:
            cur.execute(f"ALTER TABLE protection_settings ADD COLUMN {name} {sql}")
        except Exception:
            pass

    conn.commit()
    conn.close()


def get_settings(guild_id: int) -> dict:
    ensure_schema()

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO protection_settings (guild_id,updated_at) VALUES (?,?)",
        (int(guild_id), int(time.time())),
    )
    conn.commit()
    cur.execute("SELECT * FROM protection_settings WHERE guild_id=?", (int(guild_id),))
    row = cur.fetchone()
    conn.close()

    data = dict(row) if row else {}
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)

    return data


def update_settings(guild_id: int, data: dict):
    ensure_schema()

    vals = {}
    for k in DEFAULTS.keys():
        if k in data:
            vals[k] = data[k]

    if not vals:
        return

    conn = db()
    cur = conn.cursor()
    sets = ", ".join([f"{k}=?" for k in vals]) + ", updated_at=?"
    params = list(vals.values()) + [int(time.time()), int(guild_id)]
    cur.execute(f"UPDATE protection_settings SET {sets} WHERE guild_id=?", params)
    conn.commit()
    conn.close()


def get_default_bad_words():
    return DEFAULTS["bad_words"]


def normalize(text):
    text = str(text or "").lower()
    repl = {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ـ": ""}

    for a, b in repl.items():
        text = text.replace(a, b)

    # IMPORTANT: spaces are preserved. We never join words together.
    text = re.sub(r"[^a-z0-9\u0600-\u06FF]+", " ", text)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def list_from_text(value):
    return [x.strip() for x in str(value or "").replace("\n", ",").split(",") if x.strip()]


def int_set_from_text(value):
    return {int(x) for x in list_from_text(value) if str(x).isdigit()}


def matched_bad_word(text, words):
    msg = normalize(text)
    tokens = set(msg.split())

    for raw in words:
        w = normalize(raw)

        if not w:
            continue

        parts = w.split()

        if len(parts) == 1:
            # Single bad word must be standalone.
            if parts[0] in tokens:
                return raw
        else:
            # Phrase must be complete phrase, not substring.
            pat = r"(?<![\w\u0600-\u06FF])" + r"\s+".join(re.escape(p) for p in parts) + r"(?![\w\u0600-\u06FF])"
            if re.search(pat, msg):
                return raw

    return ""


def contains_bad(text, words):
    return bool(matched_bad_word(text, words))


def is_ignored_channel(settings, channel_id: int) -> bool:
    return int(channel_id) in int_set_from_text(settings.get("ignored_channels"))


def is_whitelisted_member(settings, member) -> bool:
    role_ids = int_set_from_text(settings.get("whitelist_roles"))
    if not role_ids:
        return False
    return any(int(getattr(role, "id", 0)) in role_ids for role in getattr(member, "roles", []))


def link_allowed_by_whitelist(text, settings):
    whitelist = [x.lower() for x in list_from_text(settings.get("link_whitelist"))]
    if not whitelist:
        return False
    lower = str(text or "").lower()
    return any(domain and domain in lower for domain in whitelist)


def has_link(text, settings=None):
    raw = str(text or "")

    if settings and link_allowed_by_whitelist(raw, settings):
        return False

    if re.search(r"https?://|www\.", raw, re.I):
        return True

    if settings and int(settings.get("invite_block_enabled", 1) or 0):
        if re.search(r"(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)", raw, re.I):
            return True

    return False


def is_mass_mention(message, settings):
    threshold = max(1, int(settings.get("mention_threshold", 6) or 6))
    count = len(getattr(message, "mentions", []) or []) + len(getattr(message, "role_mentions", []) or [])

    content = str(getattr(message, "content", "") or "")
    if "@everyone" in content or "@here" in content:
        count += threshold

    return count >= threshold, count


def is_caps_abuse(text, settings):
    if not int(settings.get("caps_enabled", 0) or 0):
        return False, 0

    raw = str(text or "")
    letters = [c for c in raw if c.isalpha()]

    if len(letters) < int(settings.get("caps_min_length", 18) or 18):
        return False, 0

    upper = sum(1 for c in letters if c.isupper())
    percent = int((upper / max(1, len(letters))) * 100)
    return percent >= int(settings.get("caps_percent", 85) or 85), percent


def is_newline_spam(text, settings):
    if not int(settings.get("max_newlines_enabled", 0) or 0):
        return False, 0

    count = str(text or "").count("\n")
    return count > int(settings.get("max_newlines", 12) or 12), count


def is_rate_spam(guild_id, user_id, settings):
    if not int(settings.get("spam_enabled", 1) or 0):
        return False, 0

    threshold = max(2, int(settings.get("spam_threshold", 6) or 6))
    window = max(2, int(settings.get("spam_window", 8) or 8))

    now = time.time()
    key = (int(guild_id), int(user_id))
    q = _message_times[key]
    q.append(now)

    while q and now - q[0] > window:
        q.popleft()

    return len(q) >= threshold, len(q)


def is_duplicate_spam(guild_id, user_id, content, settings):
    if not int(settings.get("duplicate_enabled", 1) or 0):
        return False, 0

    threshold = max(2, int(settings.get("duplicate_threshold", 4) or 4))
    window = max(2, int(settings.get("duplicate_window", 15) or 15))

    now = time.time()
    key = (int(guild_id), int(user_id))
    q = _duplicate_messages[key]
    norm = normalize(content)

    if not norm:
        return False, 0

    q.append((now, norm))

    while q and now - q[0][0] > window:
        q.popleft()

    count = sum(1 for _, value in q if value == norm)
    return count >= threshold, count


def check_message(message, settings):
    content = str(getattr(message, "content", "") or "")
    words = [w.strip() for w in str(settings.get("bad_words") or "").split(",") if w.strip()]

    if int(settings.get("bad_words_enabled", 1) or 0):
        match = matched_bad_word(content, words)
        if match:
            return {"blocked": True, "warning": True, "kind": "bad_word", "reason": "استخدام كلمة ممنوعة في السيرفر", "matched": match, "details": f"Matched bad word: {match}"}

    if int(settings.get("links_enabled", 1) or 0) and has_link(content, settings):
        return {"blocked": True, "warning": False, "kind": "link", "reason": "إرسال رابط أو دعوة ممنوعة", "matched": "", "details": "Blocked link/invite"}

    if int(settings.get("mass_mention_enabled", 1) or 0):
        bad, count = is_mass_mention(message, settings)
        if bad:
            return {"blocked": True, "warning": True, "kind": "mass_mention", "reason": "منشنات كثيرة أو منشن everyone/here", "matched": str(count), "details": f"Mentions count: {count}"}

    bad, percent = is_caps_abuse(content, settings)
    if bad:
        return {"blocked": True, "warning": False, "kind": "caps", "reason": "استخدام كابس بشكل مزعج", "matched": f"{percent}%", "details": f"Caps percent: {percent}%"}

    bad, newlines = is_newline_spam(content, settings)
    if bad:
        return {"blocked": True, "warning": False, "kind": "newlines", "reason": "رسالة فيها أسطر كثيرة جدًا", "matched": str(newlines), "details": f"Newlines: {newlines}"}

    guild = getattr(message, "guild", None)
    author = getattr(message, "author", None)

    if guild and author:
        bad, dup_count = is_duplicate_spam(guild.id, author.id, content, settings)
        if bad:
            return {"blocked": True, "warning": True, "kind": "duplicate_spam", "reason": "تكرار نفس الرسالة أكثر من مرة", "matched": str(dup_count), "details": f"Duplicate count: {dup_count}"}

        bad, rate_count = is_rate_spam(guild.id, author.id, settings)
        if bad:
            return {"blocked": True, "warning": True, "kind": "spam", "reason": "سبام رسائل بسرعة عالية", "matched": str(rate_count), "details": f"Messages in window: {rate_count}"}

    return {"blocked": False, "warning": False, "kind": "", "reason": "", "matched": "", "details": ""}
