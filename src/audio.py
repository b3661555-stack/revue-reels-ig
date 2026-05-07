"""Synthesize English audio narration via Azure TTS."""
import os
from pathlib import Path
import azure.cognitiveservices.speech as speechsdk


VOICE = os.environ.get("AZURE_VOICE_NAME", "en-US-AvaMultilingualNeural")


def synthesize_with_music(text: str, output_path: Path) -> None:
    key = os.environ.get("AZURE_TTS_KEY")
    region = os.environ.get("AZURE_TTS_REGION", "eastus")

    if not key:
        raise ValueError("AZURE_TTS_KEY not set")

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = VOICE

    speech_rate = os.environ.get("PROSODY_RATE", "-5%")
    ssml = f"""<speak version='1.0' xml:lang='en-US'>
        <voice xml:lang='en-US' name='{VOICE}'>
            <prosody rate='{speech_rate}'>{text}</prosody>
        </voice>
    </speak>"""

    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_path))
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )

    try:
        result = synthesizer.speak_ssml(ssml)
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"Audio synthesized: {output_path}")
        else:
            raise Exception(f"Synthesis failed: {result.reason}")
    except Exception as e:
        print(f"Azure TTS error: {e}")
        raise
