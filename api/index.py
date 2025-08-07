# api/index.py

import os
import io
import logging
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from gtts import gTTS
from googletrans import Translator

# --- Configuration ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- Models ---
class TTSRequest(BaseModel):
    text: str
    lang_code: str

# --- Frontend Endpoint ---
@app.get("/")
async def serve_frontend(request: Request):
    """Serves the main HTML user interface."""
    return templates.TemplateResponse("index.html", {"request": request})

# --- API Endpoints ---
@app.post("/translate/")
async def translate_text_only(
    text: str = Form(...),
    input_lang_code: str = Form(...),
    output_lang_code: str = Form(...)
):
    """Translates text and returns the result. Does not handle audio."""
    try:
        translator = Translator()
        translated_text = translator.translate(text, src=input_lang_code, dest=output_lang_code).text
        return {
            "original_text": text,
            "translated_text": translated_text,
            "output_lang_code": output_lang_code
        }
    except Exception as e:
        logging.error(f"Error during translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/text-to-speech/")
async def generate_speech(request: TTSRequest):
    """Generates speech from text and streams the audio back."""
    try:
        tts = gTTS(request.text, lang=request.lang_code)
        
        # Save to an in-memory file-like object
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0) # IMPORTANT: Rewind the file pointer to the beginning
        
        return StreamingResponse(mp3_fp, media_type="audio/mpeg")
    except Exception as e:
        logging.error(f"Error during TTS generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))