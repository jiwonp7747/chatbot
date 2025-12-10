import uvicorn
from fastapi import FastAPI
from config import middleware_config
import sse.chat_router as chat_router

app = FastAPI()

middleware_config.set_cors_config(app)
app.include_router(chat_router.router)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)