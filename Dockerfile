# 使用官方的 Ubuntu 20.04 镜像作为基础镜像
FROM ubuntu:20.04

# 添加作者标签
LABEL authors="zcp00"

# 禁用交互模式并设置时区，防止安装过程中提示交互
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y python3.8 python3-pip mysql-client curl && \
    apt-get install -y libglib2.0-0 && \
    apt-get install -y libgl1-mesa-glx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 更换 npm 源为淘宝镜像源
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get install -y nodejs && \
    npm config set registry https://registry.npmmirror.com

# 创建工作目录
WORKDIR /app

# 复制当前目录的内容到工作目录
COPY . /app

# 安装 Python 依赖
RUN pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 安装 Playwright
RUN playwright install --with=msedge

# 创建一个用于存储数据的目录
RUN mkdir -p /app/browser_data
RUN mkdir -p /app/img_store

# 暴露应用运行的端口（例如5000）
EXPOSE 5000

# 设置容器启动时运行的命令，保持容器运行
ENTRYPOINT ["top", "-b"]

# 如果你希望应用在容器启动时自动运行，取消以下注释并注释掉 CMD 上一行
#CMD ["python3", "main.py"]
