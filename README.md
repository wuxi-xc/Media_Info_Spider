```bash
docker run \
-d \
-it \
-p 9300:1233 \
-p 9200:1235 \ 
--restart='always' \
-v /data/gitlab/config:/etc/gitlab \
-v /data/var/log/gitlab:/var/log/gitlab \
-v /data/gitlab/data:/var/opt/gitlab \
--name gitlab \
gitlab/gitlab-ce:8.16.7-ce.0 \
python app.py
```