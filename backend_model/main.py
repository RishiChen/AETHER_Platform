from pathlib import Path
import shutil

from fastapi import (
    FastAPI,
    UploadFile,
    File
)

from AI.semantic_search.search import (
    SemanticSearch
)


# =============================================
# CREATE FASTAPI APPLICATION
# =============================================

app = FastAPI(
    title="Satellite AI Backend"
)


# =============================================
# LOAD SEMANTIC SEARCH
# =============================================

semantic_search = SemanticSearch()


# =============================================
# IMAGE DIRECTORY
# =============================================

IMAGE_DIR = Path(
    "AI/semantic_search/data/images"
)

IMAGE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =============================================
# HOME
# =============================================

@app.get("/")
def home():

    return {
        "message":
            "Satellite AI Backend Running"
    }


# =============================================
# UPLOAD IMAGE
# =============================================

@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...)
):

    # =========================================
    # GET NEXT IMAGE ID
    # =========================================

    existing_ids = [

        int(image_id)

        for image_id
        in semantic_search.metadata.keys()
    ]

    if existing_ids:

        image_id = (
            max(existing_ids) + 1
        )

    else:

        image_id = 1

    # =========================================
    # CREATE FILE NAME
    # =========================================

    filename = (
        f"{image_id}_{file.filename}"
    )

    image_path = (
        IMAGE_DIR / filename
    )

    # =========================================
    # SAVE ACTUAL IMAGE
    # =========================================

    with open(
        image_path,
        "wb"
    ) as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    # =========================================
    # CREATE EMBEDDING
    # AND STORE IN FAISS
    # =========================================

    result = (
        semantic_search.add_image(
            image_path,
            image_id
        )
    )

    # =========================================
    # RESPONSE
    # =========================================

    return {

        "message":
            "Image uploaded successfully",

        "image_id":
            result["image_id"],

        "filename":
            result["filename"]
    }


# =============================================
# SEMANTIC SEARCH
# =============================================

@app.get("/search")
def search_images(
    query: str,
    top_k: int = 5
):

    results = (
        semantic_search.search(
            query,
            top_k
        )
    )

    return {

        "query":
            query,

        "results":
            results
    }