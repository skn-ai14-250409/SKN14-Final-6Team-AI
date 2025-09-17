from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid, imghdr, os

router = APIRouter(prefix="/api/upload", tags=["upload"])


BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = (BASE_DIR / "static" / "uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_DIR = (BASE_DIR / "static" / "uploads" / "audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {"jpeg", "png", "gif", "bmp", "webp", "jpg"}
MAX_MB = 20
CHUNK_SIZE = 1024 * 1024

@router.post("/image")
async def upload_image(
    image: UploadFile = File(...),
    user_id: str | None = Form(None),
    session_id: str | None = Form(None),
):

    if not image:
        return JSONResponse({"error": "파일이 비었습니다."}, status_code=400)

    suffix = Path(image.filename).suffix.lower()

    tmp_name = f"tmp_{uuid.uuid4().hex}{suffix or ''}"
    tmp_path = UPLOAD_DIR / tmp_name
    written = 0

    try:
      with tmp_path.open("wb") as f:
          while True:
              chunk = await image.read(CHUNK_SIZE)
              if not chunk:
                  break
              f.write(chunk)
              written += len(chunk)
              if written > MAX_MB * 1024 * 1024:
                  try: tmp_path.unlink()
                  except: pass
                  return JSONResponse({"error": f"최대 {MAX_MB}MB까지만 업로드 가능합니다."}, status_code=413)

      kind = imghdr.what(tmp_path)
      if kind not in ALLOWED_TYPES:
          try: tmp_path.unlink()
          except: pass
          return JSONResponse({"error": "이미지 파일만 업로드할 수 있습니다."}, status_code=400)

      final_name = f"{uuid.uuid4().hex}.{kind if kind != 'jpeg' else 'jpg'}"
      final_path = UPLOAD_DIR / final_name
      tmp_path.rename(final_path)

      return {"url": f"/static/uploads/{final_name}"}

    except Exception as e:
      try:
          if tmp_path.exists(): tmp_path.unlink()
      except:
          pass
      return JSONResponse({"error": f"업로드 실패: {e}"}, status_code=500)



@router.post("/audio")
async def upload_audio(
    audio: UploadFile = File(...),
    user_id: str | None = Form(None),
    session_id: str | None = Form(None),
):
    if not audio:
        return JSONResponse({"error": "오디오가 비었습니다."}, status_code=400)

    ext = Path(audio.filename).suffix.lower() or ".webm"
    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = AUDIO_DIR / fname

    try:
        with fpath.open("wb") as f:
            f.write(await audio.read())

        text = ""

        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu")
            segments, info = model.transcribe(str(fpath), language="ko")
            text = "".join(seg.text for seg in segments).strip()
        except Exception:

            pass

        return {"url": f"/static/uploads/audio/{fname}", "text": text}
    except Exception as e:
        if fpath.exists():
            try: os.remove(fpath)
            except: pass
        return JSONResponse({"error": f"오디오 업로드 실패: {e}"}, status_code=500)
