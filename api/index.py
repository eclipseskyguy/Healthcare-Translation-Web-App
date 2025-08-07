# api/index.py

import os
import uuid
import logging
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from gtts import gTTS
from googletrans import Translator
from cryptography.fernet import Fernet

# --- Configuration ---
app = FastAPI()

# Setup for serving HTML templates
templates = Jinja2Templates(directory="templates")

# Load the persistent encryption key from environment variables
key_from_env = os.getenv("ENCRYPTION_KEY")
if not key_from_env:
    # This will stop the app from starting if the key is not set.
    # It's better than failing on the first request.
    raise RuntimeError("FATAL: ENCRYPTION_KEY not found in environment variables.")
cipher = Fernet(key_from_env.encode())

# Vercel provides a writable /tmp directory
TMP_DIR = "/tmp"

# --- Frontend Endpoint ---

@app.get("/")
async def serve_frontend(request: Request):
    """Serves the main HTML user interface."""
    return templates.TemplateResponse("index.html", {"request": request})

# --- API Endpoints ---

@app.post("/translate/")
async def translate_and_speak(
    text: str = Form(...),
    input_lang_code: str = Form(...),
    output_lang_code: str = Form(...)
):
    """Translates text, generates audio, encrypts it, and returns a link."""
    try:
        translator = Translator()
        translated_text = translator.translate(text, src=input_lang_code, dest=output_lang_code).text

        tts = gTTS(translated_text, lang=output_lang_code)
        audio_filename = f"{uuid.uuid4()}.mp3"
        temp_audio_path = os.path.join(TMP_DIR, audio_filename)
        tts.save(temp_audio_path)

        with open(temp_audio_path, "rb") as file:
            encrypted_data = cipher.encrypt(file.read())
        
        with open(temp_audio_path, "wb") as file:
            file.write(encrypted_data)
        
        return JSONResponse({
            "original_text": text,
            "translated_text": translated_text,
            "audio_filename": audio_filename
        })

    except Exception as e:
        logging.error(f"Error during translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Serves a decrypted audio file."""
    encrypted_path = os.path.join(TMP_DIR, filename)
    
    if not os.path.exists(encrypted_path):
        raise HTTPException(status_code=404, detail="Audio file not found or has expired.")

    try:
        with open(encrypted_path, "rb") as file:
            encrypted_data = file.read()
        
        decrypted_data = cipher.decrypt(encrypted_data)
        
        decrypted_path = os.path.join(TMP_DIR, f"decrypted_{filename}")
        with open(decrypted_path, "wb") as file:
            file.write(decrypted_data)

        return FileResponse(decrypted_path, media_type="audio/mp3", filename=filename)
        
    except Exception as e:
        logging.error(f"Error serving audio {filename}: {e}")
        raise HTTPException(status_code=500, detail="Could not decrypt or serve audio file.")