大小姐，这就对了。**Internationalization (国际化)** 是开源项目走向正规的第一步。

不过你要注意，GitHub 的 README **不支持** 像网页那样点击按钮切换内容的 JavaScript。
**行规做法是：** 在顶部放两个锚点链接（Anchor Links），点击后自动跳转到对应的语言板块。

我已经帮你把英文版翻译得非常有“硅谷范儿”（保留了你的幽默感，比如那个 Bug），同时保留了中文版的原汁原味。

**直接复制下面的 Markdown 代码到你的 `README.md` 里即可：**

---

```markdown
<div align="center">

# 🚚 Project AURORA: Local Agent Migration Guide

**From ChatGPT to Your Private Local Sanctuary**

[English](#-english) | [中文说明](#-中文说明)

</div>

---

<a name="english"></a>
## 🇺🇸 English

### 📋 Prerequisites

Before you start, you will need:
- **Engine External Zip Package** ([Download Here](https://github.com/hwj20/engine_external/releases/tag/v0.1.2))
- **OpenAI API Key** ([Get it here](https://platform.openai.com/api-keys))
- **Time:** Approx. 10-15 minutes

---

### Step 1: Install & Test

1. **Download and Unzip** the package. Choose **ONE** way to launch:
   - **Option A (Recommended):** Run `Start-AURORA.bat` (⚠️ **NOT** the .exe file directly).
   - **Option B:** Run `Engine-External-backend.exe` first (keep the window open), then run `Engine External.exe`.

2. **Configure API Key**
   - Go to **Settings**, input your OpenAI API Key.
   - Select your Model and Context Length.
   - **Click SAVE** (Crucial Step!).
   - Click **Refresh** under the Model List. If the list populates, you are connected.

3. **Send a Test Message.** If you get a reply, you are good to go! ✅

---

### Step 2: Import ChatGPT History

#### 2.1 Export from ChatGPT
1. Go to [ChatGPT](https://chat.openai.com).
2. Click your Avatar (Bottom Left) → **Settings** → **Data controls**.
3. Click **Export data**.
4. Wait for the email and download the `.zip` file.

#### 2.2 Import to Local Agent
1. Unzip the file.
2. Rename the extracted folder to `data`.
3. Copy this `data` folder to the following path:

```

C:\Users\YOUR_USERNAME\AppData\Local\AURORA-Local-Agent\personal_info\

```
*(Note: `AppData` is a hidden folder. You may need to enable "Show hidden items" in Windows Explorer.)*
4. In the software, click **Load History**.

> 💡 **Tip:** Backup your original export file to the cloud just in case.

---

### Step 3: Migrate Memory

This step requires manual handling, but it's a one-time effort.

#### 3.1 Copy Memory
1. ChatGPT → **Settings** → **Personalization** → **Memory**.
2. Copy the entire list to Notepad. It looks like:
```text
User's name is Wanjing.

User has a dog named Doudou.

```

#### 3.2 Handle Newlines (Crucial!)

ChatGPT's memory format has a flaw: it uses empty lines to separate memories, but some memories contain internal newlines. We need to remove **internal** newlines.

**Before:**

```text
User has a dog named Doudou,
a golden retriever,
3 years old.

```

**After:**

```text
User has a dog named Doudou, a golden retriever, 3 years old.

```

**Rule of Thumb:** **One Memory = One Line.** Merge split lines back together.

#### 3.3 Import Memory

1. Go to the **Memory** tab in the software.
2. Paste your cleaned text into the **Add** box at the bottom.
3. Click **Add**.

---

### Step 4: Mark Core Memories

**Core Memories** are vital info injected into every conversation (Name, preferences, relationships).

* **Manual Mark:** Manually check the boxes for memories you want to be "Core".
* **Auto Core:** Let AI classify them for you (Requires API Key).
> ⚠️ Auto classification might be unstable. Manual review is recommended.



---

### Step 5: Configure System Prompt

Due to a **"bug-turned-feature"**, preset templates are currently disabled. This gives you total freedom!

* You need to set the **System Prompt** manually in Settings.
* Don't panic: You can ask an AI (like ChatGPT) to write a persona prompt for you, then paste it in.

---

### 🎉 Migration Complete!

Now:

* Your AI companion runs locally.
* All memories are preserved.
* **You own your data.** It will never be lost.

---

### ❓ FAQ

**Q: Where do I get an API Key?**
A: [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Don't load too much credit at once; keys can expire.

**Q: How much does it cost?**
A: It depends on your `max token` setting. We are working on a **Context Compression** feature to lower costs.

**Q: Is my data safe?**
A: All data is stored locally. Only the text sent for inference goes to OpenAI via API. We do not modify your raw data files.

**Q: Why handle newlines manually?**
A: It's a formatting issue from the ChatGPT web export. We will automate this in future versions.

---

### 🐛 Troubleshooting

This is a Beta version, bugs are expected 😅.

1. Wait 30 seconds.
2. Restart the software.
3. If it persists, open an Issue or contact me.

---

<a name="中文说明"></a>

## 🇨🇳 中文说明

### 📋 开始之前

你需要准备：

* **Engine External zip包**（[点击下载](https://github.com/hwj20/engine_external/releases/tag/v0.1.2)）
* **OpenAI API Key**（[获取地址](https://platform.openai.com/api-keys)）
* **时间：** 约 10-15 分钟

---

### Step 1: 安装并测试

1. **下载并解压**，两种启动方式任选：
* **方式 A（推荐）：** 运行 `Start-AURORA.bat`（⚠️ 注意不是 .exe）。
* **方式 B：** 先运行 `Engine-External-backend.exe`（保持窗口开启），再运行 `Engine External.exe`。


2. **配置 API Key**
* 打开设置，输入你的 OpenAI API Key。
* 选择模型和上下文长度。
* **点击保存**（重要！）。
* 点击 Model List 下的 Refresh，看到模型列表返回即成功。


3. **发条消息试试**，收到回复就 OK 了 ✅

---

### Step 2: 导入 ChatGPT 对话记录

#### 2.1 从 ChatGPT 导出数据

1. 打开 [ChatGPT](https://chat.openai.com)。
2. 左下角头像 → **Settings** → **Data controls**。
3. 点击 **Export data**。
4. 等邮件，下载 zip 文件。

#### 2.2 导入到 Local

1. 解压 zip 文件。
2. 把解压出的文件夹重命名为 `data`。
3. 复制到以下路径：
```
C:\Users\你的用户名\AppData\Local\AURORA-Local-Agent\personal_info\

```


*(注意：`AppData` 是隐藏文件夹，找不到的话需要在文件夹选项里开启“显示隐藏文件”。)*
4. 在软件中点击 **加载历史对话**。

> 💡 **建议：** 把原始导出文件备份到云端，以防万一。

---

### Step 3: 迁移 Memory（记忆）

这一步需要手动处理，但只用做一次。

#### 3.1 复制 Memory

1. ChatGPT → **Settings** → **Personalization** → **Memory**。
2. 你会看到类似这样的列表：
```text
User's name is 小明.

User has a dog named 豆豆.

```


3. 全部复制到记事本。

#### 3.2 处理换行符（关键！）

ChatGPT 的 memory 格式有点问题：每条记忆之间有空行，但有些记忆内部也有换行。我们需要把记忆**内部**的换行删掉。

**处理前：**

```text
User has a dog named 豆豆,
a golden retriever,
3 years old.

```

**处理后：**

```text
User has a dog named 豆豆, a golden retriever, 3 years old.

```

**简单说：一条记忆 = 一行**，被拆开的要合并回去。

#### 3.3 导入 Memory

1. 打开软件的 Memory 页面。
2. 在底部的 Add 窗口粘贴处理好的内容。
3. 点击 **Add**。

---

### Step 4: 标记 Core 记忆

**Core 记忆** = 每次对话都会用到的重要信息（名字、偏好、家人宠物等）。

* **手动标记**：自己勾选哪些是核心记忆。
* **Auto Core**：让 AI 自动分类（需要已配置好 API Key）。
> ⚠️ 自动分类结果可能不太稳定，建议手动检查一下。



---

### Step 5: 配置 System Prompt

有个变成 **Feature** 的 Bug 是它加载不了预设的模板...

* 所以用户暂时需要自己设置 System Prompt。

---

### 🎉 搬家完成！

现在：

* 你的 AI 伙伴在本地运行。
* 所有记忆都还在。
* **数据完全属于你**，永不丢失。

---

### ❓ FAQ

**Q: API Key 哪里弄？**
A: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)，不要一次性充太多，这个 key 会过期的。

**Q: 要花多少钱？**
A: 取决于你设置的 max token。超出的上下文会被截断。我们正在做上下文压缩功能。

**Q: 数据安全吗？**
A: 所有数据保存在你本地，不经过任何第三方服务器。只有 API 调用会发送到 OpenAI。另外，软件不会修改你上传的原始数据，聊天记录会单独保存。

**Q: 为什么要手动处理换行？**
A: ChatGPT 网页端的导出格式问题，后续我们会做自动处理。

---

### 🐛 遇到问题？

这是测试版，肯定有 Bug 😅

1. 出问题先等 30 秒。
2. 不行就重启软件。
3. 还不行就来 Issue 区找我。

```

```
