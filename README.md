## 说明
* DISCORD_TOKEN: F12 开发工具 → Network → 选项 Science → Authorization 的值
* SLIMENODES_COOKIE: F12 → 应用 → cookie → Connect_sid 的值
* 提取 DISCORD_TOKEN 时，不要退出 DISCORD , 而是直接关闭浏览器页面
# V2RAY_CONFIG JSON 模板
## VMess (WS + TLS) 模板
```
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "mixed"
    }
  ],
  "outbounds": [
    {
      "protocol": "vmess",
      "settings": {
        "vnext": [
          {
            "address": "你的节点域名或IP",
            "port": 443,
            "users": [
              {
                "id": "你的UUID",
                "alterId": 0,
                "security": "auto"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "tlsSettings": {
          "serverName": "你的伪装域名(SNI)"
        },
        "wsSettings": {
          "path": "/你的WS路径",
          "host": "你的伪装域名(SNI)"
        }
      }
    }
  ]
}
```
## Trojan (TCP + TLS) 模板
```
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "mixed"
    }
  ],
  "outbounds": [
    {
      "protocol": "trojan",
      "settings": {
        "servers": [
          {
            "address": "你的节点域名",
            "port": 443,
            "password": "你的Trojan密码"
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "tls",
        "tlsSettings": {
          "serverName": "你的伪装域名(SNI)"
        }
      }
    }
  ]
}
```
## Shadowsocks 模板
```
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "mixed"
    }
  ],
  "outbounds": [
    {
      "protocol": "shadowsocks",
      "settings": {
        "servers": [
          {
            "address": "你的节点IP或域名",
            "port": 8388,
            "method": "aes-256-gcm", 
            "password": "你的SS密码"
          }
        ]
      }
    }
  ]
}
```
