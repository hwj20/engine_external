<div align="center">

# 🚚 ChatGPT Migration Guide (Official Release)

</div>

### 📋 Before You Start

You will need:

* **Engine External zip package** ([Click to download](https://github.com/hwj20/engine_external/releases/latest))
* **OpenAI API Key** ([Get it here](https://platform.openai.com/api-keys))
* **Time:** Approx. 10-15 minutes

---

### Step 1: Installation and Testing

1. **Download and install**
2. **Configure API Key**
<img width="1779" height="1522" alt="59f2e34d258bc48c92fbb5f5c42e7da8" src="https://github.com/user-attachments/assets/9c54c93d-a852-466a-93e4-7c2d7b64583d" />

3. **Send a test message**. If you get a reply, you're all set ✅

---

### Step 2: Migrate Memory
<img width="1778" height="1523" alt="22dda29aedd610f2c5695f629e1088c8" src="https://github.com/user-attachments/assets/7828b68b-2055-4b08-9cec-d6d7549b74cb" />


#### Step 2.1: Mark Core Memories

**Core Memories** = Important information used in every conversation (names, preferences, family, pets, etc.).

* **Manual Marking**: Manually check which memories are core.
* **Auto Core**: Let AI categorize automatically (requires configured API Key).

> ⚠️ Auto-categorization results might be unstable; manual review is recommended.

---

### Step 3: Import ChatGPT Chat History

#### 3.1 Export Data from ChatGPT

1. Open [ChatGPT](https://chat.openai.com).
2. Bottom left avatar → **Settings** → **Data controls**.
3. Click **Export data**.
4. Wait for the email and download the zip file.

#### 3.2 Import to Local

> 💡 **Suggestion:** Back up your original exported file to the cloud, just in case.

<img width="1775" height="1520" alt="4cff7f3f74da5d0982a674f29d3ed2b6" src="https://github.com/user-attachments/assets/98c6daad-74ce-457d-b4e4-1778b57824f4" />


---

### Step 4: Configure System Prompt

<img width="1775" height="1520" alt="a9c192326ca508e381ce5407b231093b" src="https://github.com/user-attachments/assets/7009e66a-5aee-42c9-812e-3cbd5c89dd97" />


---

### 🎉 Migration Complete!

Now:

* Your AI partner is running locally.
* All memories are intact.
* **Your data belongs entirely to you** and will never be lost.

---

### ❓ FAQ

**Q: Where do I get an API Key?**
A: [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Don't load too much credit at once; these keys expire.

**Q: How much does it cost?**
A: It depends on the "max tokens" you set. Exceeding context will be truncated. We are actively working on a context compression feature.

**Q: Is my data safe?**
A: All data is stored locally on your machine and does not pass through any third-party servers. Only API calls are sent to OpenAI. Additionally, the software will not modify your uploaded raw data; chat history is saved separately.

---

### 🐛 Encountering Issues?

I am actively maintaining the Windows version. I will also maintain the Mac version based on user feedback.
