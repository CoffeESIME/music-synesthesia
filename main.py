import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uuid

from image_analyzer import analyze_image
from hue_controller import start_hue_controller, set_state

app = FastAPI(title="Philips Hue - Image Sync")

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear directorio de uploads temporal si no existe
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    print("Iniciando controlador de Hue en segundo plano...")
    start_hue_controller()

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse(status_code=400, content={"error": "No file uploaded"})
    
    # Save file temporarily
    file_extension = file.filename.split(".")[-1]
    temp_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, temp_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Analizar la imagen
        analysis_result = analyze_image(file_path)
        
        # Enviar estado al controlador de Hue
        level = analysis_result["level"]
        colors = analysis_result["colors"]
        
        set_state(level, colors)
        
        # Eliminar archivo temporal después del análisis
        os.remove(file_path)
        
        return JSONResponse(content=analysis_result)
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/set_mode")
async def force_mode(level: int):
    # Dummy colors for testing manual mode
    test_colors = {
        1: [(255, 0, 0), (0, 0, 255)], # Rojo, Azul
        2: [(255, 255, 0), (255, 0, 255)], # Amarillo, Magenta
        3: [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
    }
    
    if level not in test_colors:
        return JSONResponse(status_code=400, content={"error": "Invalid level"})
        
    set_state(level, test_colors[level])
    return {"message": f"Modo forzado a nivel {level}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
