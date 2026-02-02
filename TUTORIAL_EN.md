# 🚚 Migrate from ChatGPT to Engine External

> Your AI companion, now truly yours - forever.

---

## 📋 Before You Start

You'll need:
- Engine External app (download from [GitHub Release](link TBD))
- Your OpenAI API Key ([get one here](https://platform.openai.com/api-keys))
- 10-15 minutes

---

## Step 1: Install and Test

1. Download and open Engine External
2. Enter your OpenAI API Key in settings
3. Send a test message
4. Got a reply? You're good! ✅

---

## Step 2: Export ChatGPT Data

### 2.1 Export from ChatGPT

1. Go to [ChatGPT](https://chat.openai.com)
2. Click your profile (bottom left) → **Settings**
3. Select **Data controls**
4. Click **Export data**
5. Wait for email, download the zip file

### 2.2 Import to Engine External

1. Unzip the downloaded file
2. Find `conversations.json`
3. Copy to Engine External's data folder:
   ```
   Windows: C:\Users\YourUsername\AppData\Local\EngineExternal\data\
   Mac: ~/Library/Application Support/EngineExternal/data/
   ```
4. Click **Load Conversations** in the app

> ⚠️ **Important**: Back up your original export to cloud storage (Google Drive, iCloud, etc.)

---

## Step 3: Migrate Memory

This step requires some manual work, but you only need to do it once.

### 3.1 Copy Memory

1. In ChatGPT → **Settings** → **Personalization** → **Memory**
2. You'll see a list like:
   ```
   User's name is Alex.
   
   User has a dog named Buddy.
   
   User prefers concise responses.
   ```
3. Select all and copy (Ctrl+A / Cmd+A, then Ctrl+C / Cmd+C)

### 3.2 Fix Line Breaks

⚠️ **Key Step**: ChatGPT's memory list has blank lines between items. But some memories also contain line breaks within them. We need to remove the line breaks **inside** each memory, keeping only the blank lines **between** memories.

**Before**:
```
User's name is Alex.

User has a dog named Buddy,
a golden retriever,
3 years old.

User prefers concise responses.
```

**After**:
```
User's name is Alex.

User has a dog named Buddy, a golden retriever, 3 years old.

User prefers concise responses.
```

Simply put: **If a single memory is split across multiple lines, merge them into one line.**

### 3.3 Save Memory File

1. Open Notepad or any text editor
2. Paste your processed memory
3. Save as `memory.txt`
4. Place in data folder:
   ```
   Windows: C:\Users\YourUsername\AppData\Local\EngineExternal\data\memory.txt
   Mac: ~/Library/Application Support/EngineExternal/data/memory.txt
   ```

---

## Step 4: Update Core Memory

1. Click **Update Core Memory** in the app
2. The app will analyze your memories and identify core ones (used in every conversation)
3. Wait for processing to complete ✅

> 💡 Core memories include: your name, key preferences, family/pet info
> 
> Other memories are retrieved intelligently when relevant

---

## 🎉 Migration Complete!

You can now:
- Continue conversations with your AI companion
- They remember everything from before
- All data stored locally - yours forever

---

## ❓ FAQ

### Q: Where do I get an API Key?
A: Visit [OpenAI API Keys](https://platform.openai.com/api-keys) and create a new key. Requires payment method.

### Q: How much does it cost?
A: Roughly $0.01-0.03 per conversation turn (GPT-4o). $10-30/month for heavy use.

### Q: Is my data safe?
A: All data stays on your local machine. Only API calls go to OpenAI.

### Q: Why do I need to manually fix memory line breaks?
A: It's a formatting quirk when copying from ChatGPT's web interface. We'll add auto-processing later.

---

## 🐛 Issues?

- Open a GitHub Issue: [link TBD]
- Or leave a comment

---

**Thanks for using Engine External!**

Your AI companion is now truly yours. 🏠
