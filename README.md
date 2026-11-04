# Shenzhen Tennis Court Check

按需查询深圳网球场空场。当前已接入：

1. 深圳金海湾店
2. 深圳金地花园店
3. 深圳南山威新店
4. 上越网球中心-沙河店
5. 康堤报业网球
6. 活力汇体育（仅查询“网球”项目，不查询“智谷”）
7. 未来荟-深圳湾体育中心（风雨棚 1–4 号、室外 5–12 号）
8. 深圳地铁文体公园（室外及遮阳网球场）
9. 塘朗运动中心
10. 威逊文体-郑洁（深圳）国际网球俱乐部
11. 威逊文体-益田网球场
12. 威逊文体-皇岗公园网球中心
13. 威逊文体-彩田公园康体中心网球场
14. 威逊文体-大沙河国际网球交流中心
15. 威逊文体-北站中心公园体育中心
16. i深体-深圳市体育中心（室外网球 1–7 号场）

工具只查询，不包含下单、占场或支付逻辑。

## 安装为 Codex 技能

```bash
git clone https://github.com/Cryptid22/shenzhen-tennis-court-check.git
mkdir -p ~/.codex/skills
ln -s "$(pwd)/shenzhen-tennis-court-check" ~/.codex/skills/shenzhen-tennis-court-check
```

也可以仅克隆后直接运行脚本。

## 使用

在 macOS 上建议明确使用系统 Python：

```bash
cd shenzhen-tennis-court-check
/usr/bin/python3 check.py
```

指定日期或时间范围（`20:00–22:00` 仅为默认值）：

```bash
/usr/bin/python3 check.py --date 2026-11-05
/usr/bin/python3 check.py --date 2026-11-05 --start 20:00 --end 22:00
```

默认日期规则：上海时间当天；如果当天是周末，或查询时已到 22:00，则顺延到下一个周一至周五。

## 输出

相邻时段会自动合并，例如：

```text
【深圳金海湾店1号场地】星期四(11-05)空场: 20:00-22:00
```

如果所有已接入场馆均无合适空场：

```text
【当前暂无合适空场】
```

接口失败会单独显示，绝不会把失败误报为“无空场”。

## 隐私

抓包文件和真实配置放在 `.private/`，已被 Git 忽略。未来荟的 `Authorization` 只保存在 `.private/config.json`（权限 `600`），不会写入源码、输出或版本库；过期时程序会明确提示重新抓包。

威逊文体不修改系统代理，也不需要 Proxyman。查询时会读取本机微信已经建立的威逊登录入口，在隔离的临时 Chrome 会话中执行威逊自己的安全校验和只读查询；临时会话在查询后自动删除。如果提示找不到微信登录凭证，重新在电脑微信打开一次“威逊文体”即可。

i深体使用公开的只读场次接口，不依赖登录凭证，不打开 Proxyman，也不修改 Clash、端口或系统代理。

## 测试

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

## Codex 技能

个人技能已安装在 `~/.codex/skills/tennis-court-check`。之后可以直接提出“查询今晚网球空场”，或指定日期和任意起止时间；技能会调用本脚本，只查询、不下单。
