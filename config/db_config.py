import os

# redis数据库,用于存储代理ip信息
REDIS_DB_HOST = "127.0.0.1"
REDIS_DB_PWD = os.getenv("REDIS_DB_PWD", "123456")

# mysql数据库，用来存储爬取的数据
RELATION_DB_PWD = os.getenv("RELATION_DB_PWD", "copycop")  # your relation db password
RELATION_DB_URL = f"mysql://copycop:{RELATION_DB_PWD}@8.130.110.140:3306/copycop"