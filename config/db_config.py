import os

# redis数据库,用于存储代理ip信息
REDIS_DB_HOST = "127.0.0.1"
REDIS_DB_PWD = os.getenv("REDIS_DB_PWD", "123456")

# mysql数据库，用来存储爬取的数据
RELATION_DB_PWD = os.getenv("RELATION_DB_PWD", "zcp.0113.")  # your relation db password
RELATION_DB_HOST = os.getenv("RELATION_DB_HOST", "root")
RELATION_DB_SERVER = os.getenv("RELATION_DB_SERVER", "127.0.0.1:3306")
RELATION_DB_NAME = os.getenv("RELATION_DB_NAME", "newdatabase")
RELATION_DB_URL = f"mysql://{RELATION_DB_HOST}:{RELATION_DB_PWD}@{RELATION_DB_SERVER}/{RELATION_DB_NAME}"