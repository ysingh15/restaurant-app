import os

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret")

    # LOCAL mode uses SQLite
    LOCAL_DB = os.getenv("LOCAL_DB", "1") == "1"

    if LOCAL_DB:
        SQLALCHEMY_DATABASE_URI = "sqlite:///local.db"
    else:
        DB_USER = os.getenv("DB_USER", "")
        DB_PASS = os.getenv("DB_PASS", "")
        DB_NAME = os.getenv("DB_NAME", "")
        CLOUD_SQL_CONNECTION_NAME = os.getenv("CLOUD_SQL_CONNECTION_NAME", "")
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@/"
            f"{DB_NAME}?host=/cloudsql/{CLOUD_SQL_CONNECTION_NAME}"
        )
