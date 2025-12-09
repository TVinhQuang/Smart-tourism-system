from deep_translator import GoogleTranslator

def translate_text(text, lang):
    if not text or lang == "vi":
        return text

    try:
        return GoogleTranslator(source='auto', target=lang).translate(text)
    except:
        return text
