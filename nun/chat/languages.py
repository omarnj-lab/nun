"""Visitor languages for the chat. The chat answers in the visitor's language; the fixed safety messages below are
written out (not model-generated) for the common visitor languages and fall back to English otherwise.

Only Arabic text and the approved English translation (Saheeh International) are shown as the verse itself. In any
other language the model *explains* the meaning from those documents and says so (`MEANING_NOTE`).
"""

from __future__ import annotations

import re

# code → (English name for the prompt, native name for the UI)
LANGUAGES: dict[str, tuple[str, str]] = {
    "ar": ("Arabic", "العربية"),
    "en": ("English", "English"),
    "fr": ("French", "Français"),
    "es": ("Spanish", "Español"),
    "de": ("German", "Deutsch"),
    "tr": ("Turkish", "Türkçe"),
    "ur": ("Urdu", "اردو"),
    "fa": ("Persian", "فارسی"),
    "id": ("Indonesian", "Bahasa Indonesia"),
    "ms": ("Malay", "Bahasa Melayu"),
    "zh": ("Chinese", "中文"),
    "ru": ("Russian", "Русский"),
    "bn": ("Bengali", "বাংলা"),
    "hi": ("Hindi", "हिन्दी"),
    "it": ("Italian", "Italiano"),
    "pt": ("Portuguese", "Português"),
    "ja": ("Japanese", "日本語"),
    "ko": ("Korean", "한국어"),
    "sw": ("Swahili", "Kiswahili"),
    "nl": ("Dutch", "Nederlands"),
}

MESSAGES: dict[str, dict[str, str]] = {
    "banner": {
        "ar": "أنا مساعد ذكي يجيب من مصادر معتمدة، ولست عالمًا أو مفتيًا.",
        "en": "I am an AI assistant that answers from approved sources. I am not a scholar or a mufti.",
        "fr": "Je suis un assistant d'IA qui répond à partir de sources approuvées. Je ne suis ni un savant ni un mufti.",
        "es": "Soy un asistente de IA que responde con fuentes aprobadas. No soy un erudito ni un muftí.",
        "de": "Ich bin ein KI-Assistent, der aus anerkannten Quellen antwortet. Ich bin kein Gelehrter und kein Mufti.",
        "tr": "Onaylı kaynaklardan yanıt veren bir yapay zekâ asistanıyım. Âlim ya da müftü değilim.",
        "ur": "میں ایک مصنوعی ذہانت کا معاون ہوں جو منظور شدہ ذرائع سے جواب دیتا ہے۔ میں عالم یا مفتی نہیں ہوں۔",
        "id": "Saya asisten AI yang menjawab dari sumber yang disetujui. Saya bukan ulama atau mufti.",
        "ms": "Saya pembantu AI yang menjawab daripada sumber yang diluluskan. Saya bukan ulama atau mufti.",
        "zh": "我是一个依据认可来源作答的人工智能助手，不是学者，也不是穆夫提。",
        "ru": "Я ИИ-помощник и отвечаю по одобренным источникам. Я не учёный и не муфтий.",
    },
    "not_found": {
        "ar": "لم أجد ما يجيب عن هذا السؤال في المصادر المعتمدة المتاحة لهذه الآية. يُستحسن سؤال مرشد أو أهل العلم.",
        "en": "I couldn't find an answer to this in the approved sources available for this verse. "
        "Please ask a guide or a qualified scholar.",
        "fr": "Je n'ai pas trouvé de réponse dans les sources approuvées disponibles pour ce verset. "
        "Veuillez demander à un guide ou à un savant qualifié.",
        "es": "No encontré la respuesta en las fuentes aprobadas disponibles para este versículo. "
        "Pregunte a un guía o a un erudito cualificado.",
        "de": "Ich habe in den verfügbaren anerkannten Quellen zu diesem Vers keine Antwort gefunden. "
        "Bitte fragen Sie einen Führer oder einen qualifizierten Gelehrten.",
        "tr": "Bu ayet için mevcut onaylı kaynaklarda bir cevap bulamadım. Lütfen bir rehbere veya ehil bir âlime sorun.",
        "ur": "اس آیت کے لیے دستیاب منظور شدہ ذرائع میں مجھے اس کا جواب نہیں ملا۔ براہِ کرم کسی رہنما یا مستند عالم سے پوچھیں۔",
        "id": "Saya tidak menemukan jawabannya dalam sumber yang disetujui untuk ayat ini. "
        "Silakan bertanya kepada pemandu atau ulama.",
        "ms": "Saya tidak menemui jawapannya dalam sumber yang diluluskan untuk ayat ini. "
        "Sila bertanya kepada pemandu atau ulama.",
        "zh": "在这节经文现有的认可来源中，我没有找到答案。请咨询导览员或合格的学者。",
        "ru": "В одобренных источниках по этому аяту я не нашёл ответа. Пожалуйста, спросите гида или знающего учёного.",
    },
    "out_of_scope": {
        "ar": "أستطيع المساعدة في فهم هذه الآية وما يتصل بها فقط.",
        "en": "I can only help with understanding this verse and closely related questions.",
        "fr": "Je peux seulement aider à comprendre ce verset et les questions qui s'y rapportent.",
        "es": "Solo puedo ayudar a entender este versículo y preguntas relacionadas.",
        "de": "Ich kann nur beim Verständnis dieses Verses und eng verwandter Fragen helfen.",
        "tr": "Yalnızca bu ayeti ve onunla ilgili soruları anlamada yardımcı olabilirim.",
        "ur": "میں صرف اس آیت اور اس سے متعلق سوالات کو سمجھنے میں مدد کر سکتا ہوں۔",
        "id": "Saya hanya dapat membantu memahami ayat ini dan pertanyaan yang terkait.",
        "ms": "Saya hanya boleh membantu memahami ayat ini dan soalan yang berkaitan.",
        "zh": "我只能帮助理解这节经文及与之密切相关的问题。",
        "ru": "Я могу помочь только с пониманием этого аята и близких к нему вопросов.",
    },
    "removed_hadith": {
        "ar": "(لم أجد حديثًا موثّقًا في المصادر المتاحة هنا.)",
        "en": "(No documented hadith is available in the sources here.)",
        "fr": "(Aucun hadith documenté n'est disponible dans les sources ici.)",
        "es": "(No hay ningún hadiz documentado en las fuentes disponibles aquí.)",
        "de": "(In den hier verfügbaren Quellen ist kein belegter Hadith vorhanden.)",
        "tr": "(Buradaki kaynaklarda belgelenmiş bir hadis bulunmuyor.)",
        "ur": "(یہاں دستیاب ذرائع میں کوئی مستند حدیث موجود نہیں۔)",
        "id": "(Tidak ada hadis terdokumentasi dalam sumber di sini.)",
        "ms": "(Tiada hadis yang didokumenkan dalam sumber di sini.)",
        "zh": "（此处来源中没有经过记载的圣训。）",
        "ru": "(В доступных здесь источниках нет задокументированного хадиса.)",
    },
    "referral": {
        "ar": "اسأل عالمًا مؤهلًا أو جهة الإفتاء الرسمية في بلدك.",
        "en": "Please ask a qualified scholar or the official fatwa authority in your country.",
        "fr": "Veuillez consulter un savant qualifié ou l'autorité officielle de fatwa de votre pays.",
        "es": "Consulte a un erudito cualificado o a la autoridad oficial de fatwas de su país.",
        "de": "Bitte wenden Sie sich an einen qualifizierten Gelehrten oder die offizielle Fatwa-Stelle Ihres Landes.",
        "tr": "Lütfen ehil bir âlime veya ülkenizdeki resmî fetva makamına danışın.",
        "ur": "براہِ کرم کسی مستند عالم یا اپنے ملک کے سرکاری دارالافتاء سے رجوع کریں۔",
        "id": "Silakan bertanya kepada ulama yang kompeten atau lembaga fatwa resmi di negara Anda.",
        "ms": "Sila rujuk ulama yang berkelayakan atau pihak berkuasa fatwa rasmi di negara anda.",
        "zh": "请咨询合格的学者或您所在国家的官方教法机构。",
        "ru": "Пожалуйста, обратитесь к квалифицированному учёному или официальному органу фетв вашей страны.",
    },
    "see_card": {
        "ar": "﴿انظر الآية في البطاقة﴾",
        "en": "(see the verse on the card)",
        "fr": "(voir le verset sur la fiche)",
        "es": "(vea el versículo en la tarjeta)",
        "de": "(siehe den Vers auf der Karte)",
        "tr": "(ayeti kartta görün)",
        "ur": "(آیت کارڈ پر دیکھیں)",
        "id": "(lihat ayat di kartu)",
        "ms": "(lihat ayat pada kad)",
        "zh": "（见卡片上的经文）",
        "ru": "(см. аят на карточке)",
    },
    "quote_removed": {  # model-written Quran text from another verse is replaced by its reference only
        "ar": "(انظر الآية {ref})",
        "en": "(see Quran {ref})",
        "fr": "(voir Coran {ref})",
        "es": "(ver Corán {ref})",
        "de": "(siehe Koran {ref})",
        "tr": "(bkz. Kur'an {ref})",
        "ur": "(دیکھیے قرآن {ref})",
        "id": "(lihat Al-Qur'an {ref})",
        "ms": "(lihat al-Quran {ref})",
        "zh": "（见古兰经 {ref}）",
        "ru": "(см. Коран {ref})",
    },
}

URDU = re.compile("[ٹڈڑںےۓھ]")  # letters Urdu uses and Arabic/Persian do not
PERSIAN = re.compile("[پچژگکی]")  # Persian letters (Arabic writes ك and ي)
SCRIPTS = [
    (URDU, "ur"),
    (PERSIAN, "fa"),
    (re.compile(r"[؀-ۿ]"), "ar"),
    (re.compile(r"[一-鿿]"), "zh"),
    (re.compile(r"[぀-ヿ]"), "ja"),
    (re.compile(r"[가-힯]"), "ko"),
    (re.compile(r"[Ѐ-ӿ]"), "ru"),
    (re.compile(r"[ঀ-৿]"), "bn"),
    (re.compile(r"[ऀ-ॿ]"), "hi"),
]


def guess(text: str) -> str:
    """Script-based fallback when the router is unavailable (Latin script → English)."""
    for pattern, code in SCRIPTS:
        if pattern.search(text):
            return code
    return "en"


def clean(code: str | None, text: str) -> str:
    code = (code or "").lower().split("-")[0].strip()
    if not re.fullmatch(r"[a-z]{2,3}", code):
        return guess(text)
    if code in ("ar", "fa", "ur") and guess(text) in ("ur", "fa"):
        return guess(text)  # same script: the letters decide (models often call Urdu or Persian "Arabic")
    return code


def name(code: str) -> str:
    return LANGUAGES.get(code, (code, code))[0]


def native(code: str) -> str:
    return LANGUAGES.get(code, (code, code))[1]


def msg(key: str, code: str, **kw: str) -> str:
    table = MESSAGES[key]
    return table.get(code, table["en"]).format(**kw)
