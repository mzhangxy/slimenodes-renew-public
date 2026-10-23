## 说明
* DISCORD_TOKEN: F12 开发工具 → Network → 选项 Science → Authorization 的值
* SLIMENODES_COOKIE: F12 → 应用 → cookie → Connect_sid 的值
* 提取 DISCORD_TOKEN 时，不要退出 DISCORD , 而是直接关闭浏览器
* CREDITS_MAX_ROUNDS: 每次运行最大收取 Credits 轮数，默认 3（在仓库 Settings → Secrets and variables → Actions → Variables 里配置）
* CREDITS_ROUND_INTERVAL: 每轮收取之间的等待秒数，默认 10（配置方式同上）
* 本工作流自动从私库拉取 main.py 并运行，脚本主体与密钥说明见私库 README
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
## Vless 模板
```
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "tag": "mixed-in",
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "mixed",
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls"]
      },
      "settings": {
        "auth": "noauth",
        "udp": true
      }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [
          {
            "address": "你的优选节点IP或域名",
            "port": 443,
            "users": [
              {
                "id": "你的UUID",
                "email": "t@t.tt",
                "encryption": "none"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "tlsSettings": {
          "allowInsecure": false,
          "serverName": "你的节点IP或域名",
          "fingerprint": "chrome"
        },
        "wsSettings": {
          "path": "/你的WS路径",
          "host": "你的节点IP或域名"
        }
      }
    },
    {
      "tag": "direct",
      "protocol": "freedom"
    },
    {
      "tag": "block",
      "protocol": "blackhole"
    }
  ]
}
