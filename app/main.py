"""FastAPI application entry point for TOFAN Smart Academy."""
from fastapi import FastAPI
from app.api.auth import router as auth_router

app = FastAPI(title="TOFAN Smart Academy", version="0.1.0")
app.include_router(auth_router)


def main() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
