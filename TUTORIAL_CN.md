# 🚚 从 ChatGPT 搬家到 Engine External 教程

> 让你的 AI 伙伴在本地永久陪伴你

---

## 📋 搬家前准备

你需要：
- Engine External 软件（从 [GitHub Release](链接待补充) 下载）
- 你的 OpenAI API Key（[获取地址](https://platform.openai.com/api-keys)）
- 10-15 分钟时间

---

## Step 1: 安装软件并测试

1. 下载并打开 Engine External,
2. 在设置中输入你的 OpenAI API Key
3. 发送一条消息测试是否正常
4. 收到回复 = 成功 ✅

![测试对话](screenshots/test_chat.png)

---

## Step 2: 导出 ChatGPT 数据

### 2.1 从 ChatGPT 导出

1. 打开 [ChatGPT](https://chat.openai.com)
2. 点击左下角头像 → **Settings**
3. 选择 **Data controls**
4. 点击 **Export data**
5. 等待邮件，下载 zip 文件

### 2.2 导入到 Engine External

1. 解压下载的 zip 文件
2. 找到 `conversations.json` 文件
3. 复制到 Engine External 的数据文件夹：
   ```
   Windows: C:\Users\你的用户名\AppData\Local\EngineExternal\data\
   Mac: ~/Library/Application Support/EngineExternal/data/
   ```
4. 在软件中点击 **加载历史对话**

> ⚠️ **重要**：建议把导出的原始数据备份到云端（Google Drive、iCloud 等），以防丢失

---

## Step 3: 迁移 Memory（记忆）

这一步稍微需要手动处理，但只需要做一次。

### 3.1 复制 Memory

1. 打开 ChatGPT → **Settings** → **Personalization** → **Memory**
2. 你会看到类似这样的记忆列表：
   ```
   User's name is 小明.
   
   User has a dog named 豆豆.
   
   User prefers concise responses.
   ```
3. 全选复制（Ctrl+A / Cmd+A，然后 Ctrl+C / Cmd+C）

### 3.2 处理换行符

⚠️ **关键步骤**：ChatGPT 的 memory 列表中，每条记忆之间有空行。但有些记忆本身也包含换行。我们需要删除记忆**内部**的换行，只保留记忆**之间**的空行。

**处理前**：
```
User's name is 小明.

User has a dog named 豆豆,
a golden retriever,
3 years old.

User prefers concise responses.
```

**处理后**：
```
User's name is 小明.

User has a dog named 豆豆, a golden retriever, 3 years old.

User prefers concise responses.
```

简单说：**如果一条记忆被拆成了多行，把它们合并成一行。**

### 3.3 保存 Memory 文件

1. 打开记事本或任意文本编辑器
2. 粘贴处理好的 memory
3. 保存为 `memory.txt`
4. 放到数据文件夹：
   ```
   Windows: C:\Users\你的用户名\AppData\Local\EngineExternal\data\memory.txt
   Mac: ~/Library/Application Support/EngineExternal/data/memory.txt
   ```

---

## Step 4: 更新 Core 记忆

1. 在软件中点击 **更新 Core 记忆**
2. 软件会自动分析你的 memory，标记哪些是核心记忆（每次对话都会用到）
3. 等待处理完成 ✅

> 💡 Core 记忆包括：你的名字、重要偏好、家人/宠物信息等
> 
> 其他记忆会通过智能检索在需要时调用

---

## 🎉 搬家完成！

现在你可以：
- 和你的 AI 伙伴继续对话
- TA 记得你之前的所有记忆
- 数据完全保存在本地，永不丢失

---

## ❓ 常见问题

### Q: API Key 从哪里获取？
A: 访问 [OpenAI API Keys](https://platform.openai.com/api-keys)，创建一个新的 key。需要绑定支付方式。

### Q: 要花多少钱？
A: 正常聊天大约 $0.01-0.03 每轮对话（使用 GPT-4o）。每月 $10-30 足够重度使用。

### Q: 数据安全吗？
A: 所有数据保存在你的本地电脑，不经过我们的服务器。只有 API 调用会发送到 OpenAI。

### Q: 为什么要手动处理 Memory 换行？
A: ChatGPT 网页端复制 memory 时的格式问题。我们后续会做自动处理工具。

---

## 🐛 遇到问题？

- 在 GitHub 提 Issue：[链接待补充]
- 或者直接在评论区留言

---

**感谢使用 Engine External！**

你的 AI 伙伴，现在真正属于你了。🏠
