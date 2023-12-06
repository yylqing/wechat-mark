# Wechat-mark

每次吃到一家好吃的店，希望可以记录下位置，就使用微信公众号进行打卡记录，可以记录地理位置、图片、文字；
- 由于普通公众号的消息没有回话概念，因此使用 Redis 服务实现多轮次对话
- 使用 sqlite 存储打卡记录

# Road Map
- [x] 实现记录
- [ ] 实现检索展示


# requirements.txt
```
werkzeug==0.16.0
wechatpy==1.8.18
cryptography==36.0.1
sanic==19.12.5
redis==4.1.1
```

# 使用方式
## 1. 使用 docker 部署
### 已有 Redis 服务器的情况
```
docker run -d \
  -p 9000:9000 \
  --name wechat-mark \
  --env-file ~/.wechat-mark/env/env.list \
  -v ~/.wechat-mark/data:/data \
  singinger/wechat-mark:0.1
```
### 使用 docker-compose.yml 成套部署
```

```

## 2. 直接使用
```
pip install -r requirements.txt
python index.py
```

# 目录结构

文件存储结构
```
~/.wechat-mark
├── data
│   ├── ass
│   │   └── o1XDp0-XXXXXXXXXXXXXXXXXX
│   │       ├── 1701766922.jpeg
│   │       ├── 1701766923.jpeg
│   │       └── 1701775667.jpeg
│   └── db
│       └── mark.db
└── env
    └── env.list
```

# 环境变量
```
--- 微信公众号配置
appid=
token=
encoding_aes_key=
AppSecret=

--- Redis 配置
redisHost=
redisPort=
redisPassword=

--- 通过token来验证可以接入的用户（给有需要的人）
allowToken=
```