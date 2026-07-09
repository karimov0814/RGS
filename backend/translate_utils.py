"""
Avtomatik tarjima yordamchisi.

Superadmin bo'lim nomini FAQAT bitta tilda (o'zi tanlagan interfeys
tilida) kiritadi — qolgan ikkita til uchun nom shu modul orqali
avtomatik tarjima qilinadi (Google Translate'ning bepul, API kalitisiz
web-endpointi orqali, `deep-translator` kutubxonasi yordamida).

Tarjima muvaffaqiyatsiz bo'lsa (masalan tarmoq xatosi), asl matn
o'zgarishsiz qaytariladi — shu bilan bo'lim "nomsiz" qolib ketmaydi,
faqat tarjima qilinmagan holda saqlanadi (admin keyinroq qo'lda
tuzatishi mumkin).
"""
import asyncio

from deep_translator import GoogleTranslator

# Bizning til kodlarimiz (uz/ru/en) deep-translator/Google Translate
# kodlari bilan bir xil, shuning uchun alohida map kerak emas.
_SUPPORTED = {"uz", "ru", "en"}


def _translate_sync(text: str, source: str, target: str) -> str:
    try:
        result = GoogleTranslator(source=source, target=target).translate(text)
        return result or text
    except Exception:
        return text


async def translate_text(text: str, source: str, target: str) -> str:
    """`text`ni `source` tildan `target` tilga tarjima qiladi. Bloklovchi
    tarmoq chaqiruvi bo'lgani uchun alohida thread'da bajariladi, shunda
    FastAPI event loop (va fon jarayoni — bot_listener) bloklanmaydi."""
    text = (text or "").strip()
    if not text or source == target or source not in _SUPPORTED or target not in _SUPPORTED:
        return text
    return await asyncio.to_thread(_translate_sync, text, source, target)


async def translate_to_all_langs(text: str, source_lang: str) -> dict:
    """Bitta tildagi matnni qolgan barcha tillarga tarjima qilib,
    {"uz": ..., "ru": ..., "en": ...} lug'atini qaytaradi (source_lang
    o'ziga tegishli qiymat — asl matnning o'zi)."""
    text = (text or "").strip()
    result = {lang: (text if lang == source_lang else None) for lang in _SUPPORTED}
    others = [lang for lang in _SUPPORTED if lang != source_lang]
    translations = await asyncio.gather(
        *[translate_text(text, source_lang, lang) for lang in others]
    )
    for lang, translated in zip(others, translations):
        result[lang] = translated
    return result
