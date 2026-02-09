# Conversations 多文件管理模块

将 OpenAI 导出的超大 `conversations.json`（几百 MB）自动拆分为单文件架构，实现毫秒级加载。

## 工作流程

1. 用户通过前端上传 OpenAI 导出的 zip 文件
2. Python 后端解压后**自动调用 `split_conversations_file()`** 拆分
3. 后续所有读写操作都通过 index.json + 单文件完成

> 无需手动运行迁移脚本，一切在上传时自动完成。

## 目录结构

```
conversations_split/
├── index.json                  # 轻量级元数据索引（~KB级）
├── conversations/
│   ├── conv_<id1>.json         # 单个对话（保留 OpenAI 原始字段）
│   ├── conv_<id2>.json
│   └── ...
└── .sync/
    └── dirty.json              # 本地修改过的对话 ID 列表
```

## 后端 API

拆分逻辑在 Python 后端 (`backend/conversations_api.py`) 中实现：

| 端点 | 说明 |
|------|------|
| `POST /upload-conversation-zip` | 上传 zip → 解压 → **自动拆分** |
| `GET /conversations/split-status` | 检查是否已完成拆分 |
| `GET /conversations` | 从 index.json 读取列表 |
| `GET /conversations/{id}` | 按需加载单个对话文件 |
| `POST /engine-conversations/save` | 保存对话到单文件 + 更新索引 |
| `POST /engine-conversations/delete/{id}` | 删除单个对话 |
| `POST /engine-conversations/reload` | 从源文件重新拆分 |

## Node.js ConversationManager（可选）

如果 Electron 主进程需要直接操作拆分后的文件（不经后端 API），
可以使用 `ConversationManager`：

```javascript
const { ConversationManager } = require('./conversations');

const manager = new ConversationManager('./conversations_split', {
  syncDebounceMs: 5000,   // 保存后 5 秒自动合并到副本
  autoSync: true,
  cacheMaxSize: 100,      // 内存缓存 100 条对话
});

// 加载索引（只读一个小文件，毫秒级）
await manager.loadIndex();

// 列出最近 20 条对话（纯内存操作）
const list = manager.listConversations({ limit: 20 });

// 搜索
const results = manager.listConversations({ query: 'AI助手' });

// 按需加载单个对话（第二次从缓存返回）
const conv = await manager.loadConversation('conv_id_xxx');

// 保存对话（立即写磁盘 + 标记dirty + 自动防抖同步）
await manager.saveConversation('my_id', convData);

// 手动同步到完整副本
await manager.syncToCopy();

// 销毁（取消定时器等）
manager.destroy();
```

### 3. 事件

```javascript
manager.on('indexLoaded',        (index) => { ... });
manager.on('conversationSaved',  ({ id, title }) => { ... });
manager.on('syncStarted',        ({ count }) => { ... });
manager.on('syncCompleted',      (result) => { ... });
manager.on('syncError',          (error) => { ... });
manager.on('titleUpdated',       ({ id, title }) => { ... });
manager.on('conversationDeleted',({ id }) => { ... });
```

## API

### `ConversationManager(baseDir, options?)`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `baseDir` | `string` | — | 多文件架构根目录 |
| `options.syncDebounceMs` | `number` | `5000` | 防抖延迟（ms） |
| `options.copyFilePath` | `string` | `.sync/conversations_full.json` | 完整副本路径 |
| `options.autoSync` | `boolean` | `true` | 保存后自动同步 |
| `options.cacheMaxSize` | `number` | `100` | 内存 LRU 缓存上限 |

### 方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `loadIndex()` | `Promise<IndexData>` | 加载索引 |
| `listConversations(opts?)` | `ConversationMeta[]` | 列表 / 搜索 / 分页 |
| `getConversationMeta(id)` | `ConversationMeta?` | 获取单条元数据 |
| `loadConversation(id)` | `Promise<object?>` | 按需加载完整对话 |
| `saveConversation(id, data)` | `Promise<void>` | 保存并标记 dirty |
| `updateTitle(id, title)` | `Promise<boolean>` | 仅更新标题 |
| `deleteConversation(id)` | `Promise<boolean>` | 删除对话 |
| `syncToCopy()` | `Promise<SyncResult>` | 手动同步到副本 |
| `getDirtyIds()` | `string[]` | 获取待同步 ID |
| `hasPendingSync()` | `boolean` | 是否有待同步更改 |
| `destroy()` | `void` | 释放资源 |

## 性能对比

| 操作 | 单文件（339 MB） | 多文件架构 |
|------|----------------|-----------|
| 加载列表 | ~3-10 秒 | ~10-50 毫秒 |
| 加载单条对话 | ~3-10 秒（整个文件） | ~5-20 毫秒 |
| 保存单条对话 | ~3-10 秒（重写整个文件） | ~5-20 毫秒 |
| 搜索标题 | ~3-10 秒 | ~1-5 毫秒（内存） |
