
### Docker启动脚本

```
docker run -d -p 5000:5000 --name media_info_container \
    -v /host/browser_data:/app/browser_data \
    -v /host/img_store:/app/img_store \
    -e PLATFORM=douyin \
    -e LOGIN_TYPE=qrcode \
    -e CRAWLER_TYPE=login \
    -e RESOURCE_NAME="庆余年2" \
    media_info
```