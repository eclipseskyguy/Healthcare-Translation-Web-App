import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
from gtts import gTTS
import tempfile
from googletrans import Translator
import logging
import os
from cryptography.fernet import Fernet
import av

# Configure Logging
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Generate a key for encryption (store securely for consistent usage)
encryption_key = Fernet.generate_key()
cipher = Fernet(encryption_key)

# Language Mapping
LANGUAGE_MAPPING = {
    "en - English": "en",
    "es - Spanish": "es",
    "fr - French": "fr",
    "de - German": "de",
    "zh - Chinese": "zh",
    "ar - Arabic": "ar",
    "hi - Hindi": "hi",
    "it - Italian": "it",
    "pt - Portuguese": "pt",
    "ru - Russian": "ru",
    "ja - Japanese": "ja",
    "ko - Korean": "ko",
    "tr - Turkish": "tr"
}

# Audio Processor for WebRTC
class AudioProcessor(AudioProcessorBase):
    def __init__(self, lang_code):
        self.lang_code = lang_code
        self.recognizer = sr.Recognizer()
        self.transcribed_text = ""

    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        audio_data = frame.to_ndarray()
        try:
            with sr.AudioFile(audio_data) as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.record(source)
                self.transcribed_text = self.recognizer.recognize_google(audio, language=self.lang_code)
        except Exception as e:
            self.transcribed_text = f"Error: {e}"
        return frame

    def get_transcribed_text(self):
        return self.transcribed_text

# Functions
def translate_text(text, input_lang_code, output_lang_code):
    """Translate text using Google Translate."""
    translator = Translator()
    return translator.translate(text, src=input_lang_code, dest=output_lang_code).text

def text_to_speech_secure(text, output_lang_code):
    """Generate audio from text and encrypt the temporary file."""
    tts = gTTS(text, lang=output_lang_code)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        tts.save(temp_audio.name)

        # Encrypt the file
        with open(temp_audio.name, "rb") as file:
            encrypted_data = cipher.encrypt(file.read())
        with open(temp_audio.name, "wb") as file:
            file.write(encrypted_data)

        return temp_audio.name

def decrypt_audio(file_path):
    """Decrypt the encrypted audio file for playback."""
    with open(file_path, "rb") as file:
        encrypted_data = file.read()
    return cipher.decrypt(encrypted_data)

def log_error(error_message):
    """Log errors with a timestamp."""
    logging.error(error_message)

# Streamlit UI Components
def render_ui():
    """Render the main UI components."""
    st.title("Healthcare Translation Web App")
    st.subheader("Real-time multilingual translation for patients and healthcare providers")

    st.sidebar.title("Settings")
    input_lang = st.sidebar.selectbox(
        "Input Language",
        list(LANGUAGE_MAPPING.keys())
    )
    output_lang = st.sidebar.selectbox(
        "Output Language",
        list(LANGUAGE_MAPPING.keys())
    )

    return input_lang, output_lang

# Main Functionality
def main():
    input_lang, output_lang = render_ui()

    input_lang_code = LANGUAGE_MAPPING[input_lang]
    output_lang_code = LANGUAGE_MAPPING[output_lang]

    st.write("Speak into your microphone for live transcription and translation.")
    webrtc_ctx = webrtc_streamer(
        key="speech-to-text",
        mode=WebRtcMode.SENDRECV,
        audio_processor_factory=lambda: AudioProcessor(input_lang_code),
        media_stream_constraints={"audio": True, "video": False},
        async_processing=True,
    )

    if webrtc_ctx.audio_processor:
        transcribed_text = webrtc_ctx.audio_processor.get_transcribed_text()
        if transcribed_text:
            st.write(f"Recognized Speech: {transcribed_text}")
            try:
                # Translate and convert to speech
                st.write("Translating...")
                translated_text = translate_text(transcribed_text, input_lang_code, output_lang_code)
                st.write(f"Translated Text: {translated_text}")

                st.write("Generating audio...")
                audio_path = text_to_speech_secure(translated_text, output_lang_code)
                decrypted_audio = decrypt_audio(audio_path)

                # Play decrypted audio
                st.audio(decrypted_audio, format="audio/mp3")

                # Clean up the encrypted file after usage
                os.remove(audio_path)

            except Exception as e:
                st.error(f"An error occurred: {e}")
                log_error(str(e))

# Run the app
if __name__ == "__main__":
    main()

