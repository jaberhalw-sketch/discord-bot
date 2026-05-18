import re, time
from nmcore.db import db
from nmcore.services.activity import log_event

OLD_DEFAULT_BAD_WORDS = "قحبه,قحبة,كس,كسمك,fuck,shit,bitch"
DEFAULT_BAD_WORDS = "قواد,خنيث,قحبه,قحبة,شرموط,شرموطه,شرموطة,سالب,كس,كس امك,كس اختك,كس اخوك,كس والديك,كسمك,كسمكم,كسمه,كسم,كسختك,كسامك,كساختك,كساخوك,كسابوك,كسس,كسي,كسى,كىس,كءس,طيزي,طيزك,طيز,انيكك,انيك,انيككك,انيك ابوك,انيك اختك,انيك اخوك,انيك امك,ازغب,جرار,معرس,اعرسك,ممحون,ممحونه,ممحونة,ممحونهه,محنه,محنة,العقه,العقة,قضي,زبي,زب,زبك,زبه,زبري,زنى,زاني,زانيه,زنوه,فقحة,فقحه,عيري,عيرك,عير,منيكه,منيوك,منيوكه,منيك,متناك,متناكه,مفتوحه,مقحب,مقحبه,ناك,نيك,مص,مصه,مصي,مصزبي,مص لين تغص,مص لين تنام,الحس,الحسيه,لحس,العق,خول,ديوث,عرص,عرصه,ياعرص,ياعرصه,قحب,قحبة*,قحبه في قحبه,يقحبه,ياقحبة,ياقحبه,بنت القحبه,يابن القحبه,يابن القحب,يابن القحاب,يابن الستين قحبه,يابن الشرموطه,يابن الشراميط,يابن المتناك,يابن المتناكه,يابن المتانيك,يابن الحرام,يبن الحرام,ابن حرام,ابن قحب,ابن قحبه,ابن الزاني,ابن الزانيه,يابن الزانيه,يا خول,يخول,يابن الخول,يابن الديوث,يابن الديوثه,ياشرموط,ياشرموطه,يازانيه,يزبي,يا ابن زبي,ياكسمك,ياكسختك,يكسمك,يامتناك,يامتناكه,يامهان,يامهانه,مهان,مهانه,جلخ,جلخت,اجلخ,اجلخ عليك,اركب عليه,اركبه,اركبي عليه,اركب على زبي,اركب علي زبي,اركب على الغالي,اركب علي الغالي,تعال اركب على زبي,على زبي,عض الغالي,تبي تتناك,تبي تمص,سكس,سكىس,سىكىس,سىكس,كلزب,كل زق يبن الشرمطه,نظام مقحبه,fuck,fucking,fucked,fucker,motherfucker,shit,bullshit,bitch,bitches,asshole,dick,cock,pussy,cunt,slut,whore,sex,suck my dick,smd,stfu,kys,3leh,3r9,3r9h,5alk,5altk,87bh,a5ok,a5tk,abok,aft7k,agl5,ajl5,al3a'le,al3'aly,al87bh,amk,anek,anekk,arkb,arkb 3leh,arkbe,arkbh,arkby,bzne,bzny,g7bh,ghbh,jtle5,ks,ks a5tk,ks-mk,ks5tk,kse,ksmk,ksy,lanek,m3r9,m7nh,m87bh,m9,mfto7,mfto7h,mhan,mhanh,mm7on,mm7onh,mnyok,mtnak,mtnakh,sharmo6h,shrame6,shrm6h,shrmo6h,shrmoth,sks,tjl5,tm9,tm9en,y87bh,ya87bh,yabn,ybn,zane,zaneh,zany,zanyh,zbe,zbo,zby,zpe,zpo,kos,kosk,kosmk,kosomk,kos omk,kos amk,zob,zeb,zebi,zebak,ayri,ayrk,eeri,3air,neek,nek,anik,aneek,aneekk,sharmoot,sharmoota,sharmouta,qahba,gahba,8ahba,9ahba,khaneeth,khaneth,5aneeth,teez,teezak,teezy,6eez,mamhon,mamhoon"

def get_default_bad_words():
    return DEFAULT_BAD_WORDS

def get_settings(guild_id:int)->dict:
    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO protection_settings (guild_id,updated_at) VALUES (?,?)", (int(guild_id), int(time.time())))
    conn.commit()

    cur.execute("SELECT * FROM protection_settings WHERE guild_id=?", (int(guild_id),))
    row = cur.fetchone()

    if row:
        data = dict(row)
        current = str(data.get("bad_words") or "").strip()

        # Auto-upgrade empty or old V9 default list into the full protection list.
        if not current or current == OLD_DEFAULT_BAD_WORDS:
            cur.execute(
                "UPDATE protection_settings SET bad_words=?, updated_at=? WHERE guild_id=?",
                (DEFAULT_BAD_WORDS, int(time.time()), int(guild_id))
            )
            conn.commit()
            data["bad_words"] = DEFAULT_BAD_WORDS

        conn.close()
        return data

    conn.close()
    return {}

def update_settings(guild_id:int, data:dict):
    old = get_settings(guild_id)
    keys = [
        "enabled",
        "bad_words_enabled",
        "links_enabled",
        "spam_enabled",
        "mass_mention_enabled",
        "delete_messages",
        "timeout_enabled",
        "bad_words",
        "ignored_channels",
        "whitelist_roles"
    ]

    vals = {}
    for k in keys:
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

def normalize(text):
    text = str(text or "").lower()

    repl = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        "ـ": "",
    }

    for a, b in repl.items():
        text = text.replace(a, b)

    # Important: do NOT remove spaces or join words together.
    # This prevents false positives like normal words containing banned substrings.
    text = re.sub(r"[^a-z0-9\u0600-\u06FF]+", " ", text)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()

def contains_bad(text, words):
    msg = normalize(text)
    tokens = set(msg.split())

    for raw in words:
        w = normalize(raw)
        if not w:
            continue

        parts = w.split()

        if len(parts) == 1:
            if parts[0] in tokens:
                return True
        else:
            pat = r"(?<![\w\u0600-\u06FF])" + r"\s+".join(re.escape(p) for p in parts) + r"(?![\w\u0600-\u06FF])"
            if re.search(pat, msg):
                return True

    return False

def matched_bad_word(text, words):
    msg = normalize(text)
    tokens = set(msg.split())

    for raw in words:
        w = normalize(raw)
        if not w:
            continue

        parts = w.split()

        if len(parts) == 1:
            if parts[0] in tokens:
                return raw
        else:
            pat = r"(?<![\w\u0600-\u06FF])" + r"\s+".join(re.escape(p) for p in parts) + r"(?![\w\u0600-\u06FF])"
            if re.search(pat, msg):
                return raw

    return ""

def has_link(text):
    return bool(re.search(r"https?://|discord\.gg/|www\.", str(text or ""), re.I))
