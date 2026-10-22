# Taiwan holidays 台灣官方休假日

以[行政院人事行政總處「中華民國政府行政機關辦公日曆表」](https://data.gov.tw/dataset/14718)為唯一來源，提供 iPhone 捷徑可直接讀取的 JSON。

資料包含政府行政機關的週末、國定假日與補假，排除官方標示的上班日。個別雇主、輪班或勞動契約的適用情況，請依自己的工作安排調整。

## 資料網址

[`data/holidays.json`](https://raw.githubusercontent.com/sunnylinisme/taiwan-holidays/main/data/holidays.json)

- `schema`: 格式版本，目前為數字 `1`。
- `generated_at`: 最後一次成功下載及驗證的 UTC 時間。
- `years`: 目前提供的西元年度；抓取當年度及下一年度。
- `valid_until_code`: 資料涵蓋的最後一天，數字 `yyyyMMdd`。
- `holidays`: 休假日，每筆包含 `date_code`、`title`、`start`、`end`、`last_second`、`marker`、`notes`。
- `cancelled`: 曾提供為休假日、後經官方改為上班日的日期，供捷徑移除其自行新增的行程。
- `sources`: 各年度官方 CSV 網址、SHA-256、總日數及休假日數。
- `warnings`: 下一年度尚未公布等狀況。既有已驗證的下一年度資料會保留。

所有日期時間都明確使用 `+08:00`。JSON 的 `end` 是通用格式的排他結束時間（隔日零時）；查找當日行程應使用 `start` 到 `last_second`，避免誤含隔日零時。

**Apple「捷徑」的「新增行程」動作在勾選整日時，開始、結束日期都應填同一天的 `start`。** 不要將 JSON 的 `end` 直接填入該動作，否則會多包含隔日。手機捷徑 v2.1 已修正此設定。

## 自動更新

GitHub Actions 每月 **28 日台灣時間 06:23** 執行，也可在 Actions → Update official holidays → Run workflow 手動更新。GitHub 的排程可能延遲，實際結果請看 Actions 狀態與 `generated_at`。

每次先跑測試，再讀取官方目錄、排除 Google 行事曆格式，並選擇檔案路徑年月較新的官方版本。程式驗證欄位、整年度每天一筆、星期、放假旗標及合理日數後，才以原子替換方式寫入 JSON。任何年度下載或格式驗證失敗都不覆蓋現有檔案。

每次成功檢查都更新時間並提交，讓使用者能確認最近檢查日期，也保持專案活動。若排程因長期失敗或 GitHub 政策而停用，請在 Actions 重新啟用。

## 手機捷徑

下載 JSON → 檢查格式版本與涵蓋日期 → 只處理今天起的日期 → 查找指定行事曆的整日行程 → 缺少時新增。

[下載公開通用版與查看安裝說明](shortcuts/README.md)。v2.0 需要 iOS 27 以上；第一次執行時詢問行事曆，之後用捷徑內建儲存記住選擇。不需填名稱，不新增設定行程或外部設定檔。各帳號間須避免同名日曆。正常逐次重跑會略過已有整日行程，請勿同時執行兩份。官方修訂的清理範圍只包含該日期、該行事曆內附註含 `TW-DGPA-GITHUB-V1:yyyyMMdd` 的捷徑行程。

此專案不接收、上傳或存放任何人的行事曆內容，也不需要 iCloud 密碼或 GitHub 個人存取權杖。手機的每月自動化請自行設定；首次執行須依 iOS 提示允許網路及行事曆存取。

## 開發與驗證

Python 3.11 以上，僅使用標準函式庫。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/update_holidays.py
```

測試包含閏年、完整年度、重複／缺漏日期、錯誤欄位、錯誤放假旗標、CSV 引號及逗號、官方修訂、修訂撤銷、下一年度暫時缺失，以及失敗時保留舊檔案。

## 資料授權

官方資料依[政府資料開放授權條款第 1 版](https://data.gov.tw/license)使用，來源機關為行政院人事行政總處；此專案是格式轉換與更新服務，並非政府官方網站。
