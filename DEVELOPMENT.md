# DEVELOPMENT

本文件面向 `astrbot_plugin_fishing` 的持续维护者与二开开发者。

它不是 AstrBot 通用插件模板说明，而是本项目当前真实架构、修复策略与扩展约定。

## 1. 项目定位

本项目是一个基于停止维护旧钓鱼插件持续演进的二开版本。

因此开发时不要默认：

- 代码结构是从零设计的
- 所有历史路径都保持一致
- SQLite 与 MySQL 两条路径都同样新鲜

请默认采用以下原则：

- **优先保运行**
- **优先保 MySQL**
- **优先保命令兼容**
- **优先把新参数接入 Web 管理与配置，而不是硬编码**

## 2. 当前主要目录

```text
astrbot_plugin_fishing/
├── main.py
├── handlers/
├── core/
│   ├── services/
│   ├── repositories/
│   ├── database/
│   └── domain/
├── draw/
├── manager/
├── metadata.yaml
├── README.md
├── CONTRIBUTING.md
└── CHANGELOG.md
```

## 3. 当前推荐开发路径

### 3.1 存储后端

当前主路径：**MySQL**

在开发新功能、修复 bug 时，请先确认：

1. MySQL 仓储是否已实现
2. MySQL 配置是否会被正确加载
3. 是否会误走 SQLite 旧路径

除兼容性修复外，不建议继续把新增能力优先堆在 SQLite 上。

### 3.2 运行入口

- 命令入口：`main.py`
- 命令处理：`handlers/`
- 业务逻辑：`core/services/`
- 数据访问：`core/repositories/`
- 图片渲染：`draw/`
- Web 管理：`manager/`

## 4. 数据库开发约定

### 4.1 MySQL 优先

如果你改了：

- 交易所
- 签到
- 商店
- 市场
- 道具/模板

请先检查对应 `Mysql*Repository` 是否同步支持。

### 4.2 避免 SQLite-only 修复

不要再新增这种类型的修复：

- 只能在 SQLite 跑的 migration 文件
- 在 MySQL 模式下仍强依赖 SQLite schema_version
- 需要手动切库才能生效的补丁

### 4.3 数据迁移策略

当需要做 SQLite -> MySQL 收敛时：

- 默认 **MySQL 是最终真源**
- 迁移时优先“补缺”而不是“覆盖”
- 避免把迁移期间新写入的 MySQL 数据回滚掉

## 5. 命令开发约定

### 5.1 命令改动必须同步检查三处

如果你新增/修改命令，请同步检查：

1. `main.py` 路由
2. 对应 `handlers/*.py`
3. `draw/help.py` 帮助内容

### 5.2 繁简体兼容

涉及面向用户的命令，建议至少覆盖：

- 主命令繁简别名
- 子命令繁简解析
- 帮助文案同步

特别是交易所、骰宝、抽卡、社交等模块。

### 5.3 不要让命令静默失败

即使失败，也要：

- 返回明确文本
- 记录错误日志
- 不要让用户看到“命令无响应”

## 6. Web 管理开发约定

当前推荐把新增玩法参数尽量接入 Web 管理。

### 6.1 适合进 Web 的内容

- 模板型配置：鱼竿、鱼饵、饰品、道具、交易所商品
- 数值型配置：价格、波动、保质期、倍率、加成
- 文案型配置：实际作用效果、描述、提示信息

### 6.2 新增项目时请一起补齐

如果新增的是可配置项目，请一起补：

- 名称
- 描述
- 数值参数
- 实际作用效果说明
- Web 管理入口

## 7. 图片渲染开发约定

### 7.1 优先保证可读性

平台压缩很常见，尤其是长图。

如果内容很多：

- 优先拆图
- 或降低信息密度
- 不要只在本地原图上看效果

### 7.2 图片失败要有日志

如果图片生成失败，至少应：

- 记录日志
- 避免拖垮整个命令流程

## 8. 当前配置重点

当前关键配置位于：

```text
data/config/astrbot_plugin_fishing_config.json
```

重点关注：

- `external_sql`
- `exchange.initial_prices`
- `exchange.volatility`
- `exchange.shelf_life_days`
- `exchange.commodity_effects`
- `item_effect_notes`

## 9. 当前已形成的维护规范

### 交易所新增商品

新增交易所商品时，至少同步补：

- `commodities`
- `exchange.initial_prices`
- `exchange.volatility`
- `exchange.shelf_life_days`
- `exchange.commodity_effects`

### 鱼竿 / 鱼饵 / 饰品新增模板

新增时建议同步补：

- 基础模板字段
- 玩家可读说明
- `item_effect_notes` 中的实际作用效果

## 10. 建议的提交流程

每次改动尽量按这个顺序：

1. 改服务或仓储
2. 改命令或 Web 层
3. 同步帮助 / 文档
4. 做最小编译检查
5. 做最小命令回归

## 11. 最后提醒

这个项目最大的风险不是“功能少”，而是“历史路径多”。

所以高质量维护的重点不是盲目加功能，而是：

- 收敛路径
- 保持一致
- 文档同步
- 让新增配置可见、可管、可验证
