<div align="center">

# 🚚 ChatGPT 搬家攻略（正式版）

[English Version](./TUTORIAL_EN.md)

</div>


### 📋 开始之前

你需要准备：

* **Engine External zip包**（[点击下载](https://github.com/hwj20/engine_external/releases/latest)）
* **OpenAI API Key**（[获取地址](https://platform.openai.com/api-keys)）
* **时间：** 约 10-15 分钟

---

### Step 1: 安装并测试

1. **下载并安装**

2. **配置 API Key**
<img width="1764" height="1364" alt="4baa00b91209d27374ef95051ab60de5" src="https://github.com/user-attachments/assets/e92fcdeb-8052-4140-aeca-17c9ea5a86bc" />

3. **发条消息试试**，收到回复就 OK 了 ✅

---

### Step 2: 迁移 Memory（记忆）

<img width="1766" height="1407" alt="8711d42e05b32e40ce15c2441f880c50" src="https://github.com/user-attachments/assets/32e652f5-5e0c-4023-bcd9-7b40763e016f" />

#### Step 2.1: 标记 Core 记忆

**Core 记忆** = 每次对话都会用到的重要信息（名字、偏好、家人宠物等）。

* **手动标记**：自己勾选哪些是核心记忆。
* **Auto Core**：让 AI 自动分类（需要已配置好 API Key）。
> ⚠️ 自动分类结果可能不太稳定，建议手动检查一下。



---

### Step 3: 导入 ChatGPT 对话记录

#### 3.1 从 ChatGPT 导出数据

1. 打开 [ChatGPT](https://chat.openai.com)。
2. 左下角头像 → **Settings** → **Data controls**。
3. 点击 **Export data**。
4. 等邮件，下载 zip 文件。

#### 3.2 导入到 Local
> 💡 **建议：** 把原始导出文件备份到云端，以防万一。


<img width="1781" height="1408" alt="be1364ba281407aa609895c762d85809" src="https://github.com/user-attachments/assets/602c9b87-f690-4f9a-9550-36654f0e95f1" />





---

### Step 4: 配置 System Prompt
<img width="1792" height="1409" alt="850dd808e3f4052cd615452feb1d563d" src="https://github.com/user-attachments/assets/3228e697-c15d-4362-8de4-cebd14f09cca" />


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


---

### 🐛 遇到问题？

Windows版我会维护，Mac版有人反馈我会维护

