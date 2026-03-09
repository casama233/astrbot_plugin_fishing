# Audit Report

本报告记录当前这轮对 `astrbot_plugin_fishing` 的集中修复、数据库收敛、命令兼容与文档更新工作。

## 1. 项目背景

本项目是基于停止维护旧钓鱼插件持续演进的 AstrBot 二开维护版本。

本轮工作的核心目标是：

- 收敛数据库主路径到 MySQL
- 修复核心命令链路
- 补齐交易所缺失商品与参数
- 扩展 Web 管理能力
- 更新文档并去隐私化

## 2. 数据库相关工作

### 2.1 MySQL 主路径收敛

- 插件当前已明确转向 MySQL 主路径
- `main.py` 中 MySQL 模式不再依赖 SQLite migration/sync 主流程
- 配置已明确以 MySQL 为当前推荐运行后端

### 2.2 SQLite -> MySQL 收敛

- 对 SQLite 与 MySQL 数据进行了差异检查
- 对关键表进行了增量补齐与收敛
- 合并了遗留交易所价格数据
- 统一当前交易所商品与价格数据到 MySQL 主库

### 2.3 数据库稳定性修复

- 修复 MySQL 连接断开后命令异常的问题
- 为 MySQL 连接管理增加自动 `ping(reconnect=True)`
- 增加读写超时配置支持

## 3. 功能修复

### 3.1 签到

- 修复 MySQL 路径下签到仓储缺失实现问题
- `/签到` 在成功与失败场景都返回明确消息

### 3.2 命运之轮

- 修复 `offset-naive and offset-aware datetimes` 混用导致的异常

### 3.3 交易所

- 修复交易所价格服务语法与逻辑问题
- 修复新商品未进入价格/渲染链路问题
- 补齐三种缺失商品：
  - `fish_bone`
  - `fish_scale`
  - `fish_sauce`
- 补齐并统一：
  - 初始价格
  - 波动率
  - 保质期
  - 实际作用效果说明
- 修复交易所子命令繁简兼容

### 3.4 帮助与图片

- `/钓鱼帮助` 改为双图输出，适配平台压缩
- 修复部分图片链路中的数据解析问题

## 4. Web 管理扩展

### 4.1 交易所管理

- 新增交易所商品参数与作用效果管理
- 支持配置：
  - `commodity_id`
  - 名称
  - 描述
  - 初始价格
  - 波动率
  - 保质期
  - 实际作用效果

### 4.2 鱼竿 / 鱼饵 / 饰品管理

- 新增“实际作用效果”字段
- 新增时即可同步填写与保存

## 5. 命令兼容与测试

### 5.1 help 命令覆盖检查

已按 `draw/help.py` 与 `main.py` 完成命令覆盖检查：

- `help.py` 展示命令全部可命中实际路由
- `ROUTABLE_MISSING = 0`

### 5.2 分类检查结果

已逐分类检查 `help.py` 中命令项的注册与处理器可达性：

- basic: PASS
- inventory: PASS
- market: PASS
- gacha: PASS
- sicbo: PASS
- social: PASS
- exchange: PASS
- admin: PASS

### 5.3 交易所繁简兼容

已支持：

- `开户 / 開戶 / 开通 / 開通`
- `买入 / 買入 / 購入`
- `卖出 / 賣出 / 出售`
- `帮助 / 幫助 / 说明 / 說明`
- `持仓 / 持倉 / 库存 / 庫存`
- `清仓 / 清倉 / 平倉`

## 6. 文档更新

本轮已更新/新增文档：

- `README.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `DEVELOPMENT.md`
- `MYSQL_MIGRATION.md`
- `DATABASE_FIX_README.md`
- `QUICK_FIX_GUIDE.md`

## 7. 去隐私化处理

本轮对文档进行了去隐私化处理：

- 不提交真实 MySQL 密码
- 不提交真实主机/IP
- 不提交真实连接串
- 不提交真实容器 ID
- 不提交明文敏感命令示例

## 8. metadata 修复

修复了 `metadata.yaml` 中 `repo` 为空导致的插件更新失败问题。

## 9. 当前结论

当前项目已完成：

- 数据库主路径收敛
- 核心命令链路修复
- 交易所扩展补齐
- Web 管理增强
- 文档体系重构与去隐私化

后续建议继续推进：

- 将更多玩法参数纳入 Web 可配置体系
- 继续收敛旧 SQLite 历史路径
- 持续完善图片渲染与平台兼容性
