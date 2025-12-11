import uvicorn
from fastapi import FastAPI
from config import middleware_config
from sse.chat_router import router as sse_router
from api.chat_session_router import router as chat_session_router
from common.exceptionhandler import register_exception_handler


app = FastAPI()

middleware_config.set_cors_config(app)
app.include_router(sse_router)
app.include_router(chat_session_router)
register_exception_handler(app)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)