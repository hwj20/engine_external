# 🚚 从 ChatGPT 搬家到 Local Agent

---

## 📋 开始之前

你需要准备：
- Engine External 的zip包（[点击下载](https://github.com/hwj20/engine_external/releases/tag/v0.1.1)）
- OpenAI API Key（[获取地址](https://platform.openai.com/api-keys)）
- 10-15 分钟

---

## Step 1: 安装并测试

1. **下载并解压**，两种启动方式任选：
   - 方式 A：运行 `Start-AURORA.bat`（注意不是 .exe）
   - 方式 B：先运行 `Engine-External-backend.exe`（保持窗口开启），再运行 `Engine External.exe`

2. **配置 API Key**
   - 打开设置，输入你的 OpenAI API Key
   - 选择模型和上下文长度
   - **点击保存**（重要！）
   - 点击 Model List 下的 Refresh，看到模型列表返回即成功

3. **发条消息试试**，收到回复就 OK 了 ✅

---

## Step 2: 导入 ChatGPT 对话记录

### 2.1 从 ChatGPT 导出数据

1. 打开 [ChatGPT](https://chat.openai.com)
2. 左下角头像 → **Settings** → **Data controls**
3. 点击 **Export data**
4. 等邮件，下载 zip 文件

### 2.2 导入到 Local

1. 解压 zip 文件
2. 把解压出的文件夹重命名为 `data`
3. 复制到以下路径：
   ```
   C:\Users\你的用户名\AppData\Local\AURORA-Local-Agent\personal_info\
   ```
4. 在软件中点击 **加载历史对话**

> 💡 建议把原始导出文件备份到云端，以防万一

---

## Step 3: 迁移 Memory（记忆）

这一步需要手动处理，但只用做一次。

### 3.1 复制 Memory

1. ChatGPT → **Settings** → **Personalization** → **Memory**
2. 你会看到类似这样的列表：
   ```
   User's name is 小明.
   
   User has a dog named 豆豆.
   
   User prefers concise responses.
   ```
3. 全部复制到记事本

### 3.2 处理换行符（关键！）

ChatGPT 的 memory 格式有点问题：每条记忆之间有空行，但有些记忆内部也有换行。我们需要把记忆**内部**的换行删掉。

**处理前：**
```
User's name is 小明.

User has a dog named 豆豆,
a golden retriever,
3 years old.

User prefers concise responses.
```

**处理后：**
```
User's name is 小明.

User has a dog named 豆豆, a golden retriever, 3 years old.

User prefers concise responses.
```

简单说：**一条记忆 = 一行**，被拆开的要合并回去。

### 3.3 导入 Memory

1. 打开软件的 Memory 页面
2. 在底部的 Add 窗口粘贴处理好的内容
3. 点击 **Add**

---

## Step 4: 标记 Core 记忆

Core 记忆 = 每次对话都会用到的重要信息（名字、偏好、家人宠物等）

两种方式：
- **手动标记**：自己选择哪些是核心记忆
- **Auto Core**：让 AI 自动分类（需要已配置好 API Key）

> ⚠️ 自动分类结果可能不太稳定，建议手动检查一下

---

## 🎉 搬家完成！

现在：
- 你的 AI 伙伴在本地运行
- 所有记忆都还在
- 数据完全属于你，永不丢失

---

## ❓ FAQ

**Q: API Key 哪里弄？**
A: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)，不要一次性充太多，这个key会过期的。

**Q: 要花多少钱？**
A: 取决于你设置的 max token。超出的上下文会被截断。我们正在做上下文压缩功能。

**Q: 数据安全吗？**
A: 所有数据保存在你本地，不经过任何第三方服务器。只有 API 调用会发送到 OpenAI。另外，软件不会修改你上传的原始数据，聊天记录会单独保存。

**Q: 为什么要手动处理换行？**
A: ChatGPT 网页端的格式问题，后续会做自动处理。

---

## 🐛 遇到问题？

这是测试版，肯定有 bug 😅

- 出问题先等 30 秒
- 不行就重启软件
- 还不行就来找我
