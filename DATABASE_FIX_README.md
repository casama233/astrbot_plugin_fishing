# 數據庫鎖定問題修復指南

## 問題描述

當您看到以下錯誤時：
- `database is locked`
- `database disk image is malformed`

這表示 SQLite 數據庫出現了鎖定或損壞問題。

## 快速修復步驟

### 方法 1：使用修復腳本（推薦）

1. 停止應用程序
2. 運行修復腳本：
```bash
python3 fix_database.py data/fish.db
```

3. 腳本會自動：
   - 創建數據庫備份
   - 檢查數據庫完整性
   - 修復損壞（如果可能）
   - 優化數據庫設置
   - 啟用 WAL 模式以提高並發性能

4. 重啟應用程序

### 方法 2：手動修復

如果修復腳本無法解決問題，可以手動操作：

1. 停止應用程序

2. 備份數據庫：
```bash
cp data/fish.db data/fish.db.backup
```

3. 使用 SQLite 命令行工具修復：
```bash
sqlite3 data/fish.db "PRAGMA integrity_check;"
sqlite3 data/fish.db "VACUUM;"
sqlite3 data/fish.db "PRAGMA journal_mode = WAL;"
sqlite3 data/fish.db "ANALYZE;"
```

4. 重啟應用程序

### 方法 3：從備份恢復

如果數據庫嚴重損壞且無法修復：

1. 查找最近的備份文件（通常在 `data/` 目錄下，文件名類似 `fish.db.backup_20260308_132800`）

2. 恢復備份：
```bash
cp data/fish.db.backup_YYYYMMDD_HHMMSS data/fish.db
```

3. 運行修復腳本優化數據庫：
```bash
python3 fix_database.py data/fish.db
```

4. 重啟應用程序

## 預防措施

為了避免將來出現類似問題：

1. **定期備份**：建議每天自動備份數據庫
   ```bash
   # 添加到 crontab
   0 2 * * * cp /path/to/data/fish.db /path/to/backups/fish.db.$(date +\%Y\%m\%d)
   ```

2. **監控數據庫大小**：如果數據庫過大（>1GB），考慮清理舊數據

3. **避免強制終止**：正常關閉應用程序，避免使用 `kill -9`

4. **檢查磁盤空間**：確保有足夠的磁盤空間

5. **使用 SSD**：如果可能，將數據庫存儲在 SSD 上以提高性能

## 已實施的優化

代碼已經進行了以下優化：

1. ✅ 增加數據庫超時時間：30秒 → 60秒
2. ✅ 啟用 WAL 模式（Write-Ahead Logging）提高並發性能
3. ✅ 設置 `busy_timeout` 為 60秒
4. ✅ 優化緩存大小（10MB）
5. ✅ 臨時數據存儲在內存中
6. ✅ 允許多線程訪問（`check_same_thread=False`）

## 常見問題

### Q: 為什麼會出現數據庫鎖定？

A: SQLite 在以下情況下可能出現鎖定：
- 多個進程同時寫入數據庫
- 長時間運行的事務未提交
- 數據庫文件損壞
- 磁盤 I/O 性能不足

### Q: WAL 模式是什麼？

A: WAL（Write-Ahead Logging）是 SQLite 的一種日誌模式，它允許讀操作和寫操作並發執行，大大提高了並發性能。

### Q: 修復後數據會丟失嗎？

A: 修復腳本會先創建備份，然後嘗試修復。如果數據庫完整性良好，不會丟失任何數據。如果數據庫嚴重損壞，可能會丟失部分最近的數據。

### Q: 如何檢查數據庫是否正常？

A: 運行以下命令：
```bash
sqlite3 data/fish.db "PRAGMA integrity_check;"
```
如果返回 "ok"，表示數據庫正常。

## 技術支持

如果問題仍然存在，請提供以下信息：
1. 錯誤日誌
2. 數據庫文件大小
3. 系統信息（操作系統、磁盤類型）
4. 並發用戶數量

## 更新日誌

- 2026-03-08: 初始版本，增加數據庫超時和優化設置
