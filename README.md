# tiny-chess 4KB Engine

一个用 Python 标准库写的国际象棋引擎，目标是在 4096 字节的硬限制下尽可能强。为 make.fun 的 tiny-chess-01 挑战而作。

## 简介

- main.py 是最终交付文件：4090 字节，LZMA + Latin-1 压缩封装，运行时解压执行
- engine.py 是对应的可读源码（15909 字节），方便阅读和修改
- pack.py 在开发机上把 engine.py 重新打包成 main.py（需要 python-minifier）

## 特性

- 0x88 棋盘表示，走子生成含易位、吃过路兵、四种升变
- 增量评估：material + PST + 双象 + 通路兵（位棋盘缓存），phase 插值王 PST
- 搜索：alpha-beta（fail-soft）+ 置换表 + quiescence + killer + MVV-LVA/PST 排序
- 固定节点预算（默认 150000），迭代加深，确定性——同一局面永远走同一着
- 处理三次重复、50 步、200 步材料裁决、子力不足等终局规则
- 通过 HTTP 与竞赛环境对话，UCI 走子

## 成绩

在本地用官方 kit 的真实对手引擎评测：

| 配置 | 官方 practice 六局 | Elo |
|---|---|---|
| 5 万节点 | 3 胜 0 和 3 负 | 1279 |
| 15 万节点 | 5 胜 0 和 1 负 | 约 1654 |

15 万节点版超过挑战的 baseline（sunfish 4KB，practice 约 1365）。同一输入用不同 PYTHONHASHSEED 跑两次，发出的走法逐字节一致，满足 replay 确定性要求。

## 运行

需要 Python 3.13 和一个兼容 make.fun env 协议的服务端。

```sh
export MAKEFUN_ENV_URL=http://127.0.0.1:18080
python3.13 -P -s main.py
wc -c main.py   # 4090
```

## 重新打包

在开发机安装 python-minifier（github.com/wenliangdeng/python-minifier），把它的 src 加入 PYTHONPATH，然后：

```sh
python3.13 pack.py
```

打包后会校验 main.py 不超过 4096 字节。

## 许可

MIT
