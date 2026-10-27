"""Generate generic test audio; online TTS only for synthetic HE/RU text."""
import asyncio
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT/'artifacts/audio'
AUDIO.mkdir(parents=True, exist_ok=True)


async def main():
    import win32com.client
    stream = win32com.client.Dispatch('SAPI.SpFileStream')
    voice = win32com.client.Dispatch('SAPI.SpVoice')
    stream.Open(str(AUDIO/'en.wav'), 3)
    voice.AudioOutputStream = stream
    voice.Speak('Hello everyone. This is an offline translation test. The tablet shows the conversation in English, Hebrew, and Russian.')
    stream.Close()
    for language, voice_name, text in [
        ('he','he-IL-HilaNeural','שלום לכולם. זהו מבחן תרגום מקומי. הטאבלט מציג את השיחה בעברית, באנגלית וברוסית.'),
        ('ru','ru-RU-SvetlanaNeural','Здравствуйте. Это проверка перевода без интернета. Планшет показывает разговор на русском, английском и иврите.')]:
        await edge_tts.Communicate(text, voice_name).save(str(AUDIO/f'{language}.mp3'))
        print(f'{language} fixture generated')


if __name__ == '__main__':
    asyncio.run(main())
