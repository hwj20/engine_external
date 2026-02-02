# 🚚 Migrate from ChatGPT to AURORA Local Agent

> Your AI companion, now truly yours.

---

## 📋 Before You Start

You'll need:
- AURORA Local Agent ([Download here](https://github.com/hwj20/engine_external/releases/tag/v0.1.1))
- OpenAI API Key ([Get one here](https://platform.openai.com/api-keys))
- 10-15 minutes

---

## Step 1: Install and Test

1. **Download and extract**. Two ways to start:
   - Option A: Run `Start-AURORA.bat` (not the .exe)
   - Option B: Run `Engine-External-backend.exe` first (keep it open), then run `Engine External.exe`

2. **Configure API Key**
   - Open Settings, enter your OpenAI API Key
   - Select model and context length
   - **Click Save** (important!)
   - Click Refresh under Model List — if models appear, you're good

3. **Send a test message**. Got a reply? You're all set ✅

---

## Step 2: Import ChatGPT Conversations

### 2.1 Export from ChatGPT

1. Go to [ChatGPT](https://chat.openai.com)
2. Profile (bottom left) → **Settings** → **Data controls**
3. Click **Export data**
4. Wait for email, download the zip

### 2.2 Import to AURORA

1. Extract the zip file
2. Rename the folder to `data`
3. Copy to:
   ```
   C:\Users\YourUsername\AppData\Local\AURORA-Local-Agent\personal_info\
   ```
4. Click **Load Conversations** in the app

> 💡 Back up your original export to cloud storage, just in case

---

## Step 3: Migrate Memory

This requires some manual work, but you only do it once.

### 3.1 Copy Memory

1. ChatGPT → **Settings** → **Personalization** → **Memory**
2. You'll see something like:
   ```
   User's name is Alex.
   
   User has a dog named Buddy.
   
   User prefers concise responses.
   ```
3. Copy everything to a text editor

### 3.2 Fix Line Breaks (Important!)

ChatGPT's memory format is tricky: there are blank lines between memories, but some memories also have line breaks inside them. We need to remove the line breaks **within** each memory.

**Before:**
```
User's name is Alex.

User has a dog named Buddy,
a golden retriever,
3 years old.

User prefers concise responses.
```

**After:**
```
User's name is Alex.

User has a dog named Buddy, a golden retriever, 3 years old.

User prefers concise responses.
```

Simply put: **One memory = one line**. Merge any that got split.

### 3.3 Import Memory

1. Open the Memory page in the app
2. Paste your processed memories in the Add box at the bottom
3. Click **Add**

---

## Step 4: Mark Core Memories

Core memories = important info used in every conversation (name, preferences, family, pets, etc.)

Two options:
- **Manual**: Mark important memories yourself
- **Auto Core**: Let AI classify them (requires API Key configured)

> ⚠️ Auto classification may not be perfect — review manually if needed

---

## 🎉 Migration Complete!

You now have:
- Your AI companion running locally
- All your memories intact
- Full ownership of your data — forever

---

## ❓ FAQ

**Q: Where do I get an API Key?**
A: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) — requires payment method

**Q: How much does it cost?**
A: Depends on your max token setting. Context beyond the limit gets truncated. We're working on context compression.

**Q: Is my data safe?**
A: All data stays on your local machine. Only API calls go to OpenAI. The app never modifies your original uploaded data — chat logs are saved separately.

**Q: Why do I need to manually fix line breaks?**
A: It's a quirk of ChatGPT's web interface. We'll add auto-processing later.

---

## 🐛 Found a Bug?

This is a beta — bugs are expected 😅

- If something breaks, wait 30 seconds
- Try restarting the app
- Still broken? Let me know

Feedback: [GitHub Issues](https://github.com/hwj20/engine_external/issues) or leave a comment

---

**Thanks for testing! Your feedback makes this better ❤️**