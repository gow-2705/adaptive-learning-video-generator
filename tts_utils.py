from gtts import gTTS

def text_to_speech(text, filename="narration.mp3", lang='en', tld='com'):
    tts = gTTS(text=text, lang=lang, tld=tld)
    tts.save(filename)
    print(f"Audio saved as {filename} with accent tld={tld}")

