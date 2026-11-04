"""Strings for the welcome window. Pure Python so tests can check it without Qt.

Each entry is (English, Simplified Chinese, Traditional Chinese (Taiwan), Japanese).
Hong Kong uses the Taiwan text with local word choices swapped in.
`%1`, `%2` are filled in by QML's String.arg().
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

# code, native name, glibc locale, Plasma LANGUAGE list
LANGUAGES = [
    ("en_US", "English", "en_US.UTF-8", "en_US"),
    ("zh_CN", "简体中文", "zh_CN.UTF-8", "zh_CN"),
    ("zh_TW", "繁體中文（台灣）", "zh_TW.UTF-8", "zh_TW"),
    ("zh_HK", "繁體中文（香港）", "zh_HK.UTF-8", "zh_HK:zh_TW"),
    ("ja_JP", "日本語", "ja_JP.UTF-8", "ja"),
]
CODES = [code for code, *_ in LANGUAGES]
HONG_KONG = {"網路": "網絡", "隨身碟": "USB 手指", "軟體": "軟件"}

STRINGS = {
    "nav_home": ("Welcome", "欢迎", "歡迎", "ようこそ"),
    "nav_tools": ("AI tools", "AI 工具", "AI 工具", "AI ツール"),
    "nav_storage": ("Encrypted storage", "加密存储", "加密儲存", "暗号化ストレージ"),
    "nav_images": ("Disk images", "磁盘镜像", "磁碟映像", "ディスクイメージ"),
    "nav_system": ("System", "系统", "系統", "システム"),
    "language": ("Language", "语言", "語言", "言語"),

    "home_title": ("Welcome to Lynux", "欢迎使用 Lynux", "歡迎使用 Lynux", "Lynux へようこそ"),
    "home_subtitle": (
        "A live Arch Linux toolbox for fixing, installing and looking after computers with AI coding agents.",
        "一个 Live Arch Linux 工具箱，配合 AI 编程助手修电脑、装系统、做日常运维。",
        "一個 Live Arch Linux 工具箱，搭配 AI 程式助手修電腦、裝系統、做日常維運。",
        "AI コーディングエージェントと一緒に、PC の修理・インストール・メンテナンスを行うための Live Arch Linux ツールボックスです。"),
    "home_status": ("Right now", "当前状态", "目前狀態", "現在の状態"),
    "home_temporary": ("Temporary session", "临时会话", "臨時工作階段", "一時セッション"),
    "home_temporary_desc": (
        "Everything is lost when you shut down. Set up encrypted storage to keep logins and files.",
        "关机后一切都会清空。建一个加密存储，就能保留登录状态和文件。",
        "關機後一切都會清空。建立加密儲存，就能保留登入狀態和檔案。",
        "シャットダウンするとすべて消えます。ログイン情報やファイルを残すには暗号化ストレージを設定してください。"),
    "home_saved": ("Encrypted storage is unlocked", "加密存储已解锁", "加密儲存已解鎖",
                   "暗号化ストレージのロックを解除済み"),
    "home_saved_desc": ("Logins and /workspace are saved to %1", "登录状态和 /workspace 会保存到 %1",
                        "登入狀態和 /workspace 會儲存到 %1", "ログイン情報と /workspace は %1 に保存されます"),
    "home_online": ("Connected to the internet", "已联网", "已連上網路", "インターネットに接続済み"),
    "home_offline": ("Not connected", "未联网", "未連上網路", "未接続"),
    "home_offline_desc": ("The AI tools need a network connection. Click to set one up.",
                          "AI 工具需要联网，点这里设置网络。", "AI 工具需要連網，點這裡設定網路。",
                          "AI ツールにはネットワーク接続が必要です。クリックして設定します。"),
    "home_start": ("Get started", "开始使用", "開始使用", "はじめる"),
    "home_tools": ("Open an AI tool", "打开 AI 工具", "開啟 AI 工具", "AI ツールを開く"),
    "home_tools_desc": ("Codex, Claude Code, Kimi Code, DeepSeek Harness and OpenCode",
                        "Codex、Claude Code、Kimi Code、DeepSeek Harness 和 OpenCode",
                        "Codex、Claude Code、Kimi Code、DeepSeek Harness 和 OpenCode",
                        "Codex、Claude Code、Kimi Code、DeepSeek Harness、OpenCode"),
    "home_storage": ("Keep your work", "保留你的工作", "保留你的工作", "作業内容を残す"),
    "home_storage_desc": ("Create or unlock encrypted storage on a USB drive or disk",
                          "在 U 盘或硬盘上创建或解锁加密存储", "在隨身碟或硬碟上建立或解鎖加密儲存",
                          "USB ドライブやディスクに暗号化ストレージを作成・ロック解除します"),
    "home_images": ("Check or open an ISO", "校验或打开 ISO", "驗證或開啟 ISO", "ISO を検証・開く"),
    "home_images_desc": ("Verify a download's SHA-256 or mount it read-only", "校验下载文件的 SHA-256，或只读挂载",
                         "驗證下載檔案的 SHA-256，或唯讀掛載",
                         "ダウンロードの SHA-256 を確認したり、読み取り専用でマウントしたりします"),
    "home_guide": ("Read the guide", "查看使用说明", "查看使用說明", "ガイドを読む"),
    "home_guide_desc": ("How Lynux works, readable offline", "离线也能看的 Lynux 使用说明",
                        "離線也能看的 Lynux 使用說明", "オフラインでも読める Lynux の使い方"),
    "home_footer": ("Sign in to each AI tool with your own account or API key.",
                    "各个 AI 工具请用你自己的账号或 API Key 登录。", "各個 AI 工具請用你自己的帳號或 API Key 登入。",
                    "各 AI ツールにはご自身のアカウントまたは API キーでサインインしてください。"),

    "tools_header": ("AI coding agents", "AI 编程助手", "AI 程式助手", "AI コーディングエージェント"),
    "tool_codex": ("OpenAI's coding agent", "OpenAI 的编程助手", "OpenAI 的程式助手", "OpenAI のコーディングエージェント"),
    "tool_claude": ("Anthropic's coding agent", "Anthropic 的编程助手", "Anthropic 的程式助手",
                    "Anthropic のコーディングエージェント"),
    "tool_kimi": ("Moonshot AI's coding agent", "月之暗面的编程助手", "月之暗面的程式助手",
                  "Moonshot AI のコーディングエージェント"),
    "tool_dsh": ("DeepSeek's agent, used in your browser", "DeepSeek 的智能体，在浏览器里使用",
                 "DeepSeek 的智慧代理，在瀏覽器裡使用", "DeepSeek のエージェント（ブラウザで使用）"),
    "tool_opencode": ("Open-source coding agent", "开源编程助手", "開源程式助手", "オープンソースのコーディングエージェント"),
    "tools_version": ("Version %1", "版本 %1", "版本 %1", "バージョン %1"),
    "tools_note": ("Each tool opens as root in its own Konsole window, starting in /workspace.",
                   "每个工具会以 root 身份在单独的 Konsole 窗口里打开，从 /workspace 开始。",
                   "每個工具會以 root 身分在獨立的 Konsole 視窗裡開啟，從 /workspace 開始。",
                   "各ツールは root として専用の Konsole ウィンドウで開き、/workspace から始まります。"),
    "tools_admin": ("Administration", "系统管理", "系統管理", "管理"),
    "tools_root": ("Root terminal", "root 终端", "root 終端機", "root ターミナル"),
    "tools_root_desc": ("A full administrator shell. Changes here affect the live system right away.",
                        "拥有完整管理员权限的 shell，在这里的改动会立刻作用于当前系统。",
                        "擁有完整管理員權限的 shell，在這裡的變更會立刻作用於目前系統。",
                        "完全な管理者シェルです。ここでの変更はすぐにライブシステムに反映されます。"),

    "storage_locked_title": ("This session is temporary", "当前是临时会话", "目前是臨時工作階段", "現在は一時セッションです"),
    "storage_locked_desc": ("Create new encrypted storage, or unlock one you made before.",
                            "新建一个加密存储，或者解锁之前建好的。", "建立新的加密儲存，或解鎖之前建好的。",
                            "新しい暗号化ストレージを作成するか、以前作成したもののロックを解除してください。"),
    "storage_unlocked_title": ("Encrypted storage is unlocked", "加密存储已解锁", "加密儲存已解鎖",
                               "暗号化ストレージのロックを解除済み"),
    "storage_usage": ("%1 used of %2", "已用 %1，共 %2", "已用 %1，共 %2", "%2 中 %1 使用"),
    "storage_create": ("Create encrypted storage…", "新建加密存储…", "建立加密儲存…", "暗号化ストレージを作成…"),
    "storage_create_desc": ("Make a password-protected file on a USB drive or disk",
                            "在 U 盘或硬盘上建一个有密码保护的文件", "在隨身碟或硬碟上建立一個有密碼保護的檔案",
                            "USB ドライブやディスクにパスワードで保護されたファイルを作ります"),
    "storage_unlock": ("Unlock…", "解锁…", "解鎖…", "ロック解除…"),
    "storage_unlock_desc": ("Open storage you created before", "打开之前建好的存储", "開啟之前建立的儲存",
                            "以前作成したストレージを開きます"),
    "storage_open_workspace": ("Open workspace", "打开工作区", "開啟工作區", "ワークスペースを開く"),
    "storage_open_workspace_desc": ("Browse /workspace in Dolphin", "在 Dolphin 中浏览 /workspace",
                                    "在 Dolphin 中瀏覽 /workspace", "Dolphin で /workspace を開きます"),
    "storage_lock": ("Lock", "锁定", "鎖定", "ロック"),
    "storage_lock_desc": ("Save everything and close the storage. You can unplug the drive afterwards.",
                          "保存所有内容并关闭存储，之后就可以拔掉 U 盘了。", "儲存所有內容並關閉儲存，之後就可以拔掉隨身碟。",
                          "すべて保存してストレージを閉じます。その後ドライブを取り外せます。"),
    "storage_found": ("Found on your drives", "在你的磁盘上找到", "在你的磁碟上找到", "ドライブで見つかったもの"),
    "storage_ventoy": ("Ventoy drive", "Ventoy 盘", "Ventoy 磁碟", "Ventoy ドライブ"),
    "ventoy_none": ("No Ventoy drive detected", "没有检测到 Ventoy 盘", "沒有偵測到 Ventoy 磁碟", "Ventoy ドライブが見つかりません"),
    "ventoy_none_desc": (
        "Lynux didn't boot from Ventoy, or its data partition isn't visible. Any other drive works too.",
        "Lynux 不是从 Ventoy 启动的，或者看不到它的数据分区。其他磁盘照样能用。",
        "Lynux 不是從 Ventoy 開機的，或看不到它的資料分割區。其他磁碟照樣能用。",
        "Lynux が Ventoy から起動していないか、データパーティションが見えません。他のドライブも使えます。"),
    "ventoy_unmounted": ("Data partition isn't mounted", "数据分区未挂载", "資料分割區未掛載",
                         "データパーティションはマウントされていません"),
    "ventoy_mount": ("Mount", "挂载", "掛載", "マウント"),
    "ventoy_readonly": ("Mounted read-only at %1", "已只读挂载到 %1", "已唯讀掛載到 %1", "%1 に読み取り専用でマウント済み"),
    "ventoy_readonly_desc": (
        "Lynux booted from this partition, so it starts read-only to be safe. Make it writable to keep storage on it.",
        "Lynux 是从这个分区启动的，为了安全先只读挂载。要在上面放加密存储，请切换为可写。",
        "Lynux 是從這個分割區開機的，為了安全先唯讀掛載。要在上面放加密儲存，請切換為可寫入。",
        "Lynux はこのパーティションから起動したため、安全のため読み取り専用です。ストレージを置くには書き込み可能にしてください。"),
    "ventoy_make_writable": ("Make writable", "切换为可写", "切換為可寫入", "書き込み可能にする"),
    "ventoy_writable": ("Mounted at %1", "已挂载到 %1", "已掛載到 %1", "%1 にマウント済み"),
    "open_folder": ("Open folder", "打开文件夹", "開啟資料夾", "フォルダを開く"),
    "storage_saved": ("What gets saved", "会保存什么", "會儲存什麼", "保存されるもの"),
    "saved_cli": ("AI tool logins and settings", "AI 工具的登录状态和设置", "AI 工具的登入狀態和設定",
                  "AI ツールのログイン情報と設定"),
    "saved_cli_desc": ("Kept separately for x86_64 and ARM64", "x86_64 和 ARM64 分开保存", "x86_64 和 ARM64 分開儲存",
                       "x86_64 と ARM64 で別々に保存"),
    "saved_workspace": ("Your files in /workspace", "/workspace 里的文件", "/workspace 裡的檔案", "/workspace 内のファイル"),
    "saved_workspace_desc": ("Shared by both architectures", "两种架构共用", "兩種架構共用", "両アーキテクチャで共有"),
    "saved_not": ("Not saved", "不保存", "不儲存", "保存されないもの"),
    "saved_not_desc": ("System changes, installed packages, desktop settings and caches",
                       "系统改动、装的软件包、桌面设置和缓存", "系統變更、安裝的套件、桌面設定和快取",
                       "システムの変更、インストールしたパッケージ、デスクトップ設定、キャッシュ"),

    "create_title": ("Create encrypted storage", "新建加密存储", "建立加密儲存", "暗号化ストレージを作成"),
    "create_drive": ("Drive:", "磁盘：", "磁碟：", "ドライブ:"),
    "create_no_drive": ("No writable drive found. Plug in a USB drive or mount a disk first.",
                        "没有找到可写的磁盘。请先插上 U 盘或挂载硬盘。", "沒有找到可寫入的磁碟。請先插上隨身碟或掛載硬碟。",
                        "書き込み可能なドライブがありません。USB ドライブを挿すか、ディスクをマウントしてください。"),
    "create_free": ("%1 free", "剩余 %1", "剩餘 %1", "空き %1"),
    "create_readonly": ("read-only", "只读", "唯讀", "読み取り専用"),
    "create_file": ("File:", "文件：", "檔案：", "ファイル:"),
    "create_file_hint": ("Inside the drive. One folder level is created for you.",
                         "相对于磁盘根目录，会自动创建一层文件夹。", "相對於磁碟根目錄，會自動建立一層資料夾。",
                         "ドライブ内の場所です。フォルダは 1 階層まで自動で作られます。"),
    "create_file_bad": ("Use a name ending in .luks, at most one folder deep.",
                        "文件名要以 .luks 结尾，最多一层文件夹。", "檔名要以 .luks 結尾，最多一層資料夾。",
                        "名前は .luks で終わり、フォルダは 1 階層までにしてください。"),
    "create_size": ("Size:", "大小：", "大小：", "サイズ:"),
    "create_size_hint": ("Up to %1 on this drive.", "这个磁盘最多能建 %1。", "這個磁碟最多能建立 %1。",
                         "このドライブでは最大 %1 です。"),
    "create_fat_hint": ("This drive is FAT32, so files must stay under 4 GiB.", "这个磁盘是 FAT32，单个文件要小于 4 GiB。",
                        "這個磁碟是 FAT32，單一檔案要小於 4 GiB。", "このドライブは FAT32 のため、ファイルは 4 GiB 未満にする必要があります。"),
    "password": ("Password:", "密码：", "密碼：", "パスワード:"),
    "password_repeat": ("Repeat:", "再输一次：", "再輸入一次：", "もう一度:"),
    "password_short": ("Use at least 8 characters.", "至少 8 个字符。", "至少 8 個字元。", "8 文字以上にしてください。"),
    "password_mismatch": ("The passwords don't match.", "两次输入的密码不一样。", "兩次輸入的密碼不一樣。",
                          "パスワードが一致しません。"),
    "create_warning": ("A forgotten password can't be recovered, and neither can the data.",
                       "忘了密码，数据就再也找不回来了。", "忘了密碼，資料就再也找不回來了。",
                       "パスワードを忘れると、データは二度と取り戻せません。"),
    "create_import": ("Anything already in /workspace, and AI tool logins from this session, moves into the new storage.",
                      "当前会话里 /workspace 的文件和 AI 工具的登录状态会搬进新存储。",
                      "目前工作階段 /workspace 的檔案和 AI 工具的登入狀態會搬進新儲存。",
                      "このセッションの /workspace のファイルと AI ツールのログイン情報は、新しいストレージに移ります。"),
    "create_button": ("Create", "创建", "建立", "作成"),
    "create_done": ("Encrypted storage is ready.", "加密存储已就绪。", "加密儲存已就緒。", "暗号化ストレージの準備ができました。"),
    "cancel": ("Cancel", "取消", "取消", "キャンセル"),
    "close": ("Close", "关闭", "關閉", "閉じる"),
    "stage_allocate": ("Reserving space… %1%", "正在分配空间… %1%", "正在配置空間… %1%", "領域を確保しています… %1%"),
    "stage_format": ("Encrypting…", "正在加密…", "正在加密…", "暗号化しています…"),
    "stage_open": ("Opening…", "正在打开…", "正在開啟…", "開いています…"),
    "stage_bind": ("Mounting…", "正在挂载…", "正在掛載…", "マウントしています…"),
    "browse": ("Browse…", "浏览…", "瀏覽…", "参照…"),

    "unlock_title": ("Unlock encrypted storage", "解锁加密存储", "解鎖加密儲存", "暗号化ストレージのロック解除"),
    "unlock_file": ("Container:", "容器：", "容器：", "コンテナ:"),
    "unlock_button": ("Unlock", "解锁", "解鎖", "ロック解除"),
    "unlock_done": ("Encrypted storage is unlocked.", "加密存储已解锁。", "加密儲存已解鎖。",
                    "暗号化ストレージのロックを解除しました。"),
    "unlock_none": ("No storage found on mounted drives. Browse for the file, or mount its drive first.",
                    "已挂载的磁盘上没找到存储。请浏览选择文件，或先挂载它所在的磁盘。",
                    "已掛載的磁碟上沒找到儲存。請瀏覽選擇檔案，或先掛載它所在的磁碟。",
                    "マウント済みのドライブにストレージがありません。ファイルを参照するか、先にドライブをマウントしてください。"),

    "holders_title": ("Programs are still using your storage", "还有程序在使用加密存储", "還有程式在使用加密儲存",
                      "まだストレージを使っているプログラムがあります"),
    "holders_desc": ("Lynux can end the ones you pick, then lock. Unsaved work in them will be lost.",
                     "Lynux 可以结束你勾选的程序，然后锁定。这些程序里没保存的内容会丢失。",
                     "Lynux 可以結束你勾選的程式，然後鎖定。這些程式裡沒儲存的內容會遺失。",
                     "選んだプログラムを終了してからロックできます。保存していない作業は失われます。"),
    "holders_still": ("These didn't close in time. Force them to quit?", "这些程序没有及时退出，要强制结束吗？",
                      "這些程式沒有及時結束，要強制結束嗎？", "これらは時間内に終了しませんでした。強制終了しますか？"),
    "holders_end": ("End selected and lock", "结束所选并锁定", "結束所選並鎖定", "選択したものを終了してロック"),
    "holders_force": ("Force quit and lock", "强制结束并锁定", "強制結束並鎖定", "強制終了してロック"),
    "holders_session": ("AI session · %1 processes", "AI 会话 · %1 个进程", "AI 工作階段 · %1 個行程",
                        "AI セッション · %1 プロセス"),
    "holders_process": ("PID %1 · user %2", "PID %1 · 用户 %2", "PID %1 · 使用者 %2", "PID %1 · ユーザー %2"),
    "locking": ("Locking…", "正在锁定…", "正在鎖定…", "ロックしています…"),
    "lock_done": ("Encrypted storage is locked. It's safe to unplug the drive.", "加密存储已锁定，可以安全拔出 U 盘了。",
                  "加密儲存已鎖定，可以安全拔出隨身碟了。", "暗号化ストレージをロックしました。ドライブを取り外して大丈夫です。"),

    "images_check": ("Check an ISO", "校验 ISO", "驗證 ISO", "ISO を検証"),
    "images_choose": ("Choose an ISO…", "选择 ISO…", "選擇 ISO…", "ISO を選択…"),
    "images_choose_desc": ("It can be anywhere: a Ventoy drive, USB stick or disk", "放在哪里都行：Ventoy 盘、U 盘或硬盘",
                           "放在哪裡都行：Ventoy 磁碟、隨身碟或硬碟", "場所はどこでも構いません：Ventoy ドライブ、USB メモリ、ディスク"),
    "images_expected": ("Expected SHA-256", "预期的 SHA-256", "預期的 SHA-256", "期待する SHA-256"),
    "images_expected_hint": ("Optional. Paste it from the download page.", "可选，从下载页面复制过来。",
                             "可選，從下載頁面複製過來。", "任意。ダウンロードページから貼り付けます。"),
    "images_verify": ("Calculate SHA-256", "计算 SHA-256", "計算 SHA-256", "SHA-256 を計算"),
    "images_hashing": ("Reading the whole file. Large ISOs take a minute or two…", "正在读取整个文件，大的 ISO 要一两分钟…",
                       "正在讀取整個檔案，大的 ISO 需要一兩分鐘…", "ファイル全体を読み込んでいます。大きな ISO は 1〜2 分かかります…"),
    "images_result": ("SHA-256", "SHA-256", "SHA-256", "SHA-256"),
    "images_match": ("Matches the expected SHA-256.", "和预期的 SHA-256 一致。", "與預期的 SHA-256 相符。",
                     "期待する SHA-256 と一致しました。"),
    "images_mismatch": ("Doesn't match the expected SHA-256. Don't use this file.", "和预期的 SHA-256 不一致，不要用这个文件。",
                        "與預期的 SHA-256 不符，請勿使用這個檔案。", "期待する SHA-256 と一致しません。このファイルは使わないでください。"),
    "images_copy": ("Copy", "复制", "複製", "コピー"),
    "images_mount": ("Mount read-only", "只读挂载", "唯讀掛載", "読み取り専用でマウント"),
    "images_mount_desc": ("Browse its contents without changing anything", "浏览里面的内容，不做任何修改",
                          "瀏覽裡面的內容，不做任何修改", "何も変更せずに中身を見ます"),
    "images_mounted": ("Mounted images", "已挂载的镜像", "已掛載的映像", "マウント中のイメージ"),
    "images_unmount": ("Unmount", "卸载", "卸載", "マウント解除"),
    "images_note": (
        "Lynux never copies, moves or writes your ISOs. To install another system, open its ISO here and ask an "
        "AI tool to walk you through it.",
        "Lynux 不会复制、移动或改写你的 ISO。要装其他系统，可以在这里打开它的 ISO，再让 AI 工具一步步带你装。",
        "Lynux 不會複製、移動或改寫你的 ISO。要安裝其他系統，可以在這裡開啟它的 ISO，再讓 AI 工具一步步帶你安裝。",
        "Lynux は ISO をコピー・移動・書き換えしません。別のシステムを入れるときは、ここで ISO を開き、AI ツールに手順を案内してもらってください。"),

    "system_language_input": ("Language and input", "语言与输入", "語言與輸入", "言語と入力"),
    "system_language_desc": ("Lynux switches right away. The rest of the desktop switches after you log out.",
                             "Lynux 会立即切换，桌面其余部分在注销后切换。", "Lynux 會立即切換，桌面其餘部分在登出後切換。",
                             "Lynux はすぐに切り替わります。デスクトップ全体はログアウト後に切り替わります。"),
    "system_input": ("Input methods", "输入法", "輸入法", "入力メソッド"),
    "system_input_desc": ("Pinyin, Zhuyin, Cangjie, Jyutping and Japanese are ready. Press Ctrl+Space to switch.",
                          "拼音、注音、仓颉、粤拼和日语都已装好，按 Ctrl+Space 切换。",
                          "拼音、注音、倉頡、粵拼和日文都已裝好，按 Ctrl+Space 切換。",
                          "ピンイン、注音、倉頡、粵拼、日本語が使えます。Ctrl+Space で切り替えます。"),
    "system_connections": ("Connections and drives", "网络与磁盘", "網路與磁碟", "ネットワークとドライブ"),
    "system_network": ("Network", "网络", "網路", "ネットワーク"),
    "system_network_desc": ("Wi-Fi, Ethernet and VPN", "Wi-Fi、有线网络和 VPN", "Wi-Fi、有線網路和 VPN", "Wi-Fi、有線、VPN"),
    "system_files": ("Files", "文件", "檔案", "ファイル"),
    "system_files_desc": ("Browse drives in Dolphin", "在 Dolphin 中浏览磁盘", "在 Dolphin 中瀏覽磁碟",
                          "Dolphin でドライブを見ます"),
    "system_partitions": ("Partition Manager", "分区管理器", "分割區管理員", "パーティションマネージャ"),
    "system_partitions_desc": ("Resize, format and check partitions", "调整、格式化和检查分区", "調整、格式化和檢查分割區",
                               "パーティションのサイズ変更・フォーマット・チェック"),
    "system_settings": ("System Settings", "系统设置", "系統設定", "システム設定"),
    "system_settings_desc": ("Display, sound, keyboard and more", "显示、声音、键盘等", "顯示、聲音、鍵盤等",
                             "ディスプレイ、サウンド、キーボードなど"),
    "system_window": ("This window", "本窗口", "本視窗", "このウィンドウ"),
    "system_autostart": ("Show at login", "登录时显示", "登入時顯示", "ログイン時に表示"),
    "system_about": ("About", "关于", "關於", "情報"),
    "system_version": ("Version", "版本", "版本", "バージョン"),
    "system_timezone": ("Time zone", "时区", "時區", "タイムゾーン"),
    "system_timezone_desc": ("UTC. Change it in System Settings if you need local time.",
                             "UTC。需要本地时间的话，可以在系统设置里改。", "UTC。需要當地時間的話，可以在系統設定裡改。",
                             "UTC です。現地時刻が必要ならシステム設定で変更してください。"),
    "system_source": ("Source code", "源代码", "原始碼", "ソースコード"),

    "lang_changed_title": ("Language changed", "语言已切换", "語言已切換", "言語を変更しました"),
    "lang_changed_desc": (
        "Lynux is now in %1. Log out to switch the rest of the desktop. Open windows, including AI tools, will close.",
        "Lynux 已切换为%1。注销后桌面其余部分也会切换，打开的窗口（包括 AI 工具）会被关闭。",
        "Lynux 已切換為%1。登出後桌面其餘部分也會切換，開著的視窗（包括 AI 工具）會被關閉。",
        "Lynux は%1になりました。ログアウトするとデスクトップ全体も切り替わります。開いているウィンドウ（AI ツールを含む）は閉じられます。"),
    "lang_logout": ("Log out now", "立即注销", "立即登出", "今すぐログアウト"),
    "lang_later": ("Later", "稍后", "稍後", "あとで"),
    "lang_system_failed": ("Couldn't change the system language: %1", "无法切换系统语言：%1", "無法切換系統語言：%1",
                           "システムの言語を変更できませんでした: %1"),
    "logout_failed": ("Couldn't log out automatically. Use Log Out in the application launcher.",
                      "无法自动注销，请在开始菜单里选择“注销”。", "無法自動登出，請在應用程式啟動器裡選擇「登出」。",
                      "自動でログアウトできませんでした。アプリケーションランチャーからログアウトしてください。"),

    "err_wrong_password": ("Wrong password.", "密码错误。", "密碼錯誤。", "パスワードが違います。"),
    "err_exists": ("%1 already exists. Pick another name. Lynux never overwrites files.",
                   "%1 已经存在，请换个名字。Lynux 不会覆盖已有文件。", "%1 已經存在，請換個名字。Lynux 不會覆寫既有檔案。",
                   "%1 は既に存在します。別の名前にしてください。Lynux は既存のファイルを上書きしません。"),
    "err_read_only": ("That drive is mounted read-only.", "这个磁盘是只读挂载的。", "這個磁碟是唯讀掛載的。",
                      "そのドライブは読み取り専用でマウントされています。"),
    "err_unsuitable_fs": ("Pick a real, writable drive.", "请选择真实、可写的磁盘。", "請選擇真實、可寫入的磁碟。",
                          "実在する書き込み可能なドライブを選んでください。"),
    "err_fat32_limit": ("FAT32 can't hold files of 4 GiB or more. Pick a smaller size.",
                        "FAT32 单个文件不能达到 4 GiB，请选小一点。", "FAT32 單一檔案不能達到 4 GiB，請選小一點。",
                        "FAT32 には 4 GiB 以上のファイルを置けません。小さめのサイズにしてください。"),
    "err_no_space": ("Not enough free space. At least 512 MiB must stay free afterwards.",
                     "空间不够，建完之后至少要剩 512 MiB。", "空間不夠，建立之後至少要剩 512 MiB。",
                     "空き容量が足りません。作成後も 512 MiB 以上の空きが必要です。"),
    "err_no_parent": ("That folder doesn't exist.", "这个文件夹不存在。", "這個資料夾不存在。", "そのフォルダは存在しません。"),
    "err_already_open": ("Encrypted storage is already open. Lock it first.", "已经有加密存储打开了，请先锁定。",
                         "已經有加密儲存開著，請先鎖定。", "暗号化ストレージは既に開いています。先にロックしてください。"),
    "err_unknown_layout": ("This isn't Lynux storage, or a newer Lynux made it. Nothing was changed.",
                           "这不是 Lynux 的存储，或者是更新版本建的。没有做任何改动。",
                           "這不是 Lynux 的儲存，或是更新版本建立的。沒有做任何變更。",
                           "Lynux のストレージではないか、新しい Lynux で作成されたものです。何も変更していません。"),
    "err_session_has_data": ("This session already has files in %1. Move them somewhere else first, so unlocking doesn't hide them.",
                             "当前会话的 %1 里已经有文件。请先把它们挪走，免得解锁后被盖住。",
                             "目前工作階段的 %1 裡已經有檔案。請先把它們移走，免得解鎖後被蓋住。",
                             "このセッションの %1 には既にファイルがあります。ロック解除で隠れないよう、先に別の場所へ移してください。"),
    "err_create_failed": ("Creating the storage failed. The unfinished file %1 was kept so you can check it.",
                          "创建失败。没建完的文件 %1 留着，方便你检查。", "建立失敗。沒建完的檔案 %1 留著，方便你檢查。",
                          "作成に失敗しました。確認できるよう、作りかけのファイル %1 は残してあります。"),
    "err_busy": ("An AI tool or root terminal is still running. Close it first.", "还有 AI 工具或 root 终端在运行，请先关闭。",
                 "還有 AI 工具或 root 終端機在執行，請先關閉。", "AI ツールまたは root ターミナルが動いています。先に閉じてください。"),
    "err_open_failed": ("Couldn't open the storage file.", "无法打开存储文件。", "無法開啟儲存檔案。",
                        "ストレージファイルを開けませんでした。"),
    "err_not_found": ("That file doesn't exist.", "文件不存在。", "檔案不存在。", "ファイルが存在しません。"),
    "err_generic": ("Something went wrong: %1", "出错了：%1", "發生錯誤：%1", "エラーが発生しました: %1"),
}

def strings(code):
    index = {"en_US": 0, "zh_CN": 1, "zh_TW": 2, "zh_HK": 2, "ja_JP": 3}[code]
    result = {}
    for key, values in STRINGS.items():
        text = values[index]
        if code == "zh_HK":
            for taiwan, hong_kong in HONG_KONG.items():
                text = text.replace(taiwan, hong_kong)
        result[key] = text
    return result


def match(value):
    """Map a locale or LANGUAGE value like 'zh_CN.UTF-8' or 'ja:en' to a supported code."""
    for item in (value or "").split(":"):
        name = item.split(".", 1)[0].split("@", 1)[0].replace("-", "_")
        if name in CODES:
            return name
        if name == "ja":
            return "ja_JP"
        if name in ("zh", "zh_SG"):
            return "zh_CN"
        if name == "zh_MO":
            return "zh_HK"
        if name.startswith("en"):
            return "en_US"
    return None


def detect(config_home=None, environ=None):
    """The language Plasma will use for this user, else the process environment, else English."""
    environ = os.environ if environ is None else environ
    config = Path(config_home or environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "plasma-localerc"
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(config, encoding="utf-8")
        found = match(parser.get("Translations", "LANGUAGE", fallback=""))
        if found:
            return found
    except configparser.Error:
        pass
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        found = match(environ.get(name, ""))
        if found:
            return found
    return "en_US"


def settings(code):
    """(glibc locale, Plasma LANGUAGE list) for a supported code."""
    for item, _, locale, language in LANGUAGES:
        if item == code:
            return locale, language
    raise ValueError(f"Unsupported language: {code}")
