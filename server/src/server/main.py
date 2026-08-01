import uvicorn
from fastapi.responses import HTMLResponse
from __init__ import app

post: list[dict] = [{"id": 1, "name": "Khanh"}, {"id": 2, "name": "Trang"}]

@app.get("/", response_class=HTMLResponse)
def home():
    return f"<h1>{post[0]['name']}</h1>"

if __name__ == "__main__":
    uvicorn.run(app)