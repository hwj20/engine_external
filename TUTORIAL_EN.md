
<div align="center">

# 🚚 Local Agent Migration Guide

**From ChatGPT to Your Private Local Sanctuary**


</div>

---



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

