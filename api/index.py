from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from gtts import gTTS
from googletrans import Translator
from cryptography.fernet import Fernet
import logging
import os
import uuid

# --- Configuration ---
app = FastAPI()



# Load the persistent encryption key from environment variables
# This is the CRUCIAL fix for a serverless environment.
key_from_env = os.getenv("ENCRYPTION_KEY")
if not key_from_env:
    raise RuntimeError("ENCRYPTION_KEY not found in environment variables. Please set it in .env.local")
cipher = Fernet(key_from_env.encode())

# Vercel provides a writable /tmp directory for serverless functions
TMP_DIR = "/tmp"

# --- API Endpoints ---

@app.post("/translate/")
async def translate_and_speak(
    text: str = Form(...),
    input_lang_code: str = Form(...),
    output_lang_code: str = Form(...)
):
    try:
        # 1. Translate Text
        translator = Translator()
        translated_text = translator.translate(text, src=input_lang_code, dest=output_lang_code).text
        logging.info(f"Translated '{text}' to '{translated_text}'")

        # 2. Generate Audio and save to a unique file in /tmp
        tts = gTTS(translated_text, lang=output_lang_code)
        # Use a unique filename to avoid conflicts
        audio_filename = f"{uuid.uuid4()}.mp3"
        temp_audio_path = os.path.join(TMP_DIR, audio_filename)
        tts.save(temp_audio_path)
        logging.info(f"Generated audio at {temp_audio_path}")

        # 3. Encrypt the audio file
        with open(temp_audio_path, "rb") as file:
            encrypted_data = cipher.encrypt(file.read())
        
        # Overwrite the original with encrypted data
        with open(temp_audio_path, "wb") as file:
            file.write(encrypted_data)
        logging.info(f"Encrypted audio file: {audio_filename}")
        
        # 4. Return the unique filename
        return JSONResponse({
            "original_text": text,
            "translated_text": translated_text,
            "audio_filename": audio_filename # Return only the filename, not the full path
        })

    except Exception as e:
        logging.error(f"Error during translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    encrypted_path = os.path.join(TMP_DIR, filename)
    
    if not os.path.exists(encrypted_path):
        raise HTTPException(status_code=404, detail="Audio file not found or has expired.")

    try:
        # 1. Read the encrypted file
        with open(encrypted_path, "rb") as file:
            encrypted_data = file.read()
        
        # 2. Decrypt the data in memory
        decrypted_data = cipher.decrypt(encrypted_data)
        logging.info(f"Decrypted audio for serving: {filename}")

        # 3. Save decrypted data to a new temp file for serving
        decrypted_path = os.path.join(TMP_DIR, f"decrypted_{filename}")
        with open(decrypted_path, "wb") as file:
            file.write(decrypted_data)

        # 4. Serve the decrypted file and clean up afterwards
        # (Cleanup is tricky; Vercel handles /tmp cleanup automatically)
        return FileResponse(decrypted_path, media_type="audio/mp3", filename=filename)
        
    except Exception as e:
        logging.error(f"Error serving audio {filename}: {e}")
        raise HTTPException(status_code=500, detail="Could not decrypt or serve audio file.")

# A root endpoint for health checks
@app.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI Medical Translator is running"}
