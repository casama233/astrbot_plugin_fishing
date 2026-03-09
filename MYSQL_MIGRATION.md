# MySQL Migration Guide

本文件用于记录当前项目从 SQLite 收敛到 MySQL 的最终操作规范与回滚建议。

本文档 **已去隐私化**，不包含任何真实：

- MySQL 主机地址
- 用户名
- 密码
- 实际连接串
- 容器名 / 实例名

请在实际执行时自行替换为你的环境变量或本地参数。

## 1. 目标

将插件运行时持久化统一到 **MySQL 主路径**，避免继续依赖 SQLite 作为主要运行数据库。

当前建议策略：

- MySQL 作为最终真源
- SQLite 仅保留兼容与导入价值
- 新增功能优先面向 MySQL 实现

## 2. 迁移原则

### 2.1 不直接覆盖 MySQL 新数据

如果迁移期间插件已经开始写入 MySQL：

- 不要直接用 SQLite 全量覆盖 MySQL
- 应优先采用“补缺 / 收敛 / 去重”策略

### 2.2 优先保留 MySQL 较新的业务数据

典型例子：

- `exchange_prices`
- `check_ins`
- `user_fish_inventory`
- `shop_purchase_records`

这些表如果 MySQL 中计数高于 SQLite，通常意味着迁移期间已产生新数据。

## 3. 推荐迁移流程

### 第一步：停写

在最终收敛前，建议：

1. 停止 AstrBot 插件或暂停外部访问
2. 确保 SQLite 与 MySQL 不再继续同时写入

### 第二步：备份

请至少备份：

- SQLite 数据库文件
- MySQL 目标数据库
- 当前插件配置文件

建议备份内容：

```text
data/fish.db
data/config/astrbot_plugin_fishing_config.json
MySQL database dump
```

### 第三步：迁移 / 补齐

推荐顺序：

1. 先导入 SQLite 基础数据到 MySQL
2. 再做差异表“补缺”而不是“覆盖”
3. 对重复敏感表建立唯一键或在导入层做去重

对于交易所价格表，推荐唯一逻辑：

```text
(date, time, commodity_id)
```

## 4. 当前项目中的关键迁移点

### 4.1 交易所商品表

需要确保 `commodities` 至少包含：

- `dried_fish`
- `fish_roe`
- `fish_oil`
- `fish_bone`
- `fish_scale`
- `fish_sauce`

### 4.2 交易所价格表

需要确保：

- `price_id` 为 `AUTO_INCREMENT`
- 不存在遗留临时表导致读错主表
- 如曾存在 `exchange_prices_new`，需合并回主表后删除

### 4.3 签到表

需要确保：

- `check_ins` 表存在
- MySQL 仓储已实现签到读写逻辑

## 5. 插件配置要求

推荐配置方向：

```json
{
  "external_sql": {
    "backend": "mysql",
    "enabled": false,
    "sync_on_startup": false,
    "mysql_url": "mysql://<username>:<password>@<host>:<port>/<database>",
    "connect_timeout": 10,
    "read_timeout": 30,
    "write_timeout": 30
  }
}
```

说明：

- `backend=mysql`：明确走 MySQL 仓储
- `enabled=false`：避免继续走旧外部同步逻辑
- `sync_on_startup=false`：避免启动时再做双向同步

## 6. 迁移后检查项

迁移完成后，至少核验：

1. 插件后端解析结果为 `mysql`
2. `users` 表可读
3. `exchange_prices` 可读
4. `check_ins` 可读
5. 交易所新商品存在
6. `help.py` 命令与主路由可达

推荐在线测试：

- `/签到`
- `/状态`
- `/交易所`
- `/持仓`
- `/命运之轮 500`

## 7. 回滚建议

如果迁移后发现严重问题，可按以下顺序回滚：

### 方案 A：快速回退到旧 SQLite 运行

1. 停止 AstrBot
2. 恢复迁移前配置文件
3. 将 `external_sql.backend` 改回 `sqlite`
4. 重启并验证基础命令

### 方案 B：回退 MySQL 数据库

1. 停止 AstrBot
2. 导入迁移前 MySQL 备份
3. 保持 `backend=mysql`
4. 重启后验证基础命令

### 方案 C：保留 MySQL，重新做“补缺式收敛”

适用于：

- MySQL 已经有新数据
- 不希望完全回滚

做法：

- 重新对比 SQLite / MySQL 关键表计数
- 只补 MySQL 缺少的数据
- 不覆盖 MySQL 已存在且更新的数据

## 8. 安全建议

请不要在仓库中提交以下内容：

- 真正的 `mysql_url`
- 明文账号密码
- 服务器 IP / 域名
- 容器 ID / 实例名
- 含真实密钥的日志或截图

建议做法：

- 文档中一律使用占位符
- 日志脱敏后再提交
- 配置文件按需本地化，不把敏感信息写入仓库

## 9. 当前结论

本项目当前的维护方向已经明确：

- **MySQL 是主路径**
- **SQLite 是兼容与导入路径**
- **迁移以收敛为目标，而不是长期双栈并行**
