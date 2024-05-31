# 使用官方的 Ubuntu 20.04 镜像作为基础镜像
FROM ubuntu:20.04

# 添加作者标签
LABEL authors="zcp00"

# 禁用交互模式并设置时区，防止安装过程中提示交互
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y python3.8 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制当前目录的内容到工作目录
COPY . /app

# 如果你有依赖文件 requirements.txt，解除注释以下两行并确保 requirements.txt 存在
RUN pip3 install --no-cache-dir -r requirements.txt

# 如果没有requirements.txt，或者想在Dockerfile中直接安装依赖，可以使用以下命令
#RUN pip3 install --no-cache-dir flask requests

# 创建一个用于存储数据的目录
RUN mkdir -p /app/browser_data
RUN mkdir -p /app/img_store

# 暴露应用运行的端口（例如5000）
EXPOSE 5000

# 如果你希望应用在容器启动时自动运行，取消以下注释并注释掉 ENTRYPOINT 上一行
CMD ["python3", "main.py"]
