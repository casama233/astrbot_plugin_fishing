# Quick Fix Guide

本文件是当前项目的快速应急指引。

## 当前建议

如果你现在遇到插件数据库相关问题，请优先确认：

1. 插件是否已配置为 `backend = mysql`
2. MySQL 是否可连接
3. 插件是否仍意外走到了旧 SQLite 路径

## 快速检查清单

### 1. 检查配置

确认配置文件中：

- `external_sql.backend = mysql`
- `external_sql.sync_on_startup = false`
- `external_sql.enabled = false`（如当前不再使用旧同步器）

### 2. 检查插件是否能启动

重点关注：

- 是否存在 MySQL 连接报错
- 是否存在仓储未实现导致的命令失败
- 是否存在图片命令因平台权限失败

### 3. 检查关键命令

建议优先测试：

- `/签到`
- `/状态`
- `/交易所`
- `/持仓`
- `/钓鱼帮助`

## 如果你是从 SQLite 迁移过来

请不要只做“SQLite 修好了就继续用”。

当前推荐做法：

- 以 MySQL 为主路径运行
- SQLite 仅保留为历史备份或导入来源

迁移规范请阅读：

- `MYSQL_MIGRATION.md`

## 典型问题与当前处理建议

### 问题 1：交易所商品不显示

优先检查：

- `commodities` 表是否存在对应商品
- `exchange.initial_prices`
- `exchange.volatility`
- `exchange.shelf_life_days`
- `exchange.commodity_effects`

### 问题 2：签到无响应

优先检查：

- MySQL 的 `check_ins` 表是否存在
- MySQL 日志仓储是否已实现签到逻辑

### 问题 3：图片命令失败

优先检查：

- 平台是否允许发送图片 / 附件
- 图片渲染是否报错
- 命令本体是否已进入 handler

### 问题 4：插件更新失败

优先检查：

- `metadata.yaml` 中是否已配置 `repo`

## 当前文档口径

本文件已统一为 **MySQL 主路径** 口径，不再把 SQLite 修复描述为默认方案。

## 安全说明

本文件已去隐私化，不包含真实：

- 数据库地址
- 用户名
- 密码
- 容器 ID
- 明文连接串
