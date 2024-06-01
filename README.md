
### Docker启动脚本

```
docker run -d -p 5000:5000 --name media_info_container \
    -v /home/aurora/app/browser_data:/app/browser_data \
    -v /home/aurora/app/img_store:/app/img_store \
    -e PLATFORM=douyin \
    -e LOGIN_TYPE=qrcode \
    -e CRAWLER_TYPE=login \
    -e RESOURCE_NAME="庆余年2" \
    media_info
```

### 项目说明

#### 1. 项目结构

1. config: 配置文件
2. libs: 依赖文件
3. media_platform: 核心代码
4. proxy: 代理
5. store: 存储
6. tools: 核心代码中使用到的工具
7. main.py: 入口文件
8. Dockerfile: Docker构建文件
9. requirements.txt: 依赖文件

#### 2. 项目功能
1. 支持多平台
2. 支持多种登录方式（账号密码、二维码、cookie）
3. 支持多种存储方式（数据库、json、csv）
4. 支持进行网络代理
5. 最大程度的全自动化（验证码自动验证）
