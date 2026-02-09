/**
 * ConversationManager — 多文件对话管理器
 *
 * 核心能力：
 *   - 加载轻量级索引（index.json）用于列表展示
 *   - 按需加载单个对话文件
 *   - 保存对话后立即写入磁盘，并标记 dirty
 *   - 异步合并 dirty 对话到完整副本文件（队列 + 防抖）
 *
 * 目录结构：
 *   <baseDir>/
 *   ├── index.json
 *   ├── conversations/
 *   │   └── conv_<id>.json
 *   └── .sync/
 *       └── dirty.json
 */

const fsp = require('fs/promises');
const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');

// ─── 类型注释（JSDoc） ────────────────────────────────────────

/**
 * @typedef {Object} ConversationMeta
 * @property {string}  id
 * @property {string}  title
 * @property {number|null} create_time
 * @property {number|null} update_time
 * @property {number}  message_count
 * @property {boolean} dirty
 */

/**
 * @typedef {Object} IndexData
 * @property {string} version
 * @property {string} last_modified
 * @property {number} total_conversations
 * @property {ConversationMeta[]} conversations
 */

/**
 * @typedef {Object} SyncResult
 * @property {boolean} success
 * @property {number}  syncedCount
 * @property {string[]} syncedIds
 * @property {string}  [error]
 */

// ─── ConversationManager ─────────────────────────────────────

class ConversationManager extends EventEmitter {
  /**
   * @param {string} baseDir - 多文件架构根目录（包含 index.json 的目录）
   * @param {Object} [options]
   * @param {number}  [options.syncDebounceMs=5000]  - 防抖延迟（毫秒）
   * @param {string}  [options.copyFilePath]          - 合并后的完整副本路径
   * @param {boolean} [options.autoSync=true]          - 是否自动触发 dirty 同步
   * @param {number}  [options.cacheMaxSize=100]       - 内存中缓存的对话数量上限
   */
  constructor(baseDir, options = {}) {
    super();
    this.baseDir = baseDir;
    this.convsDir = path.join(baseDir, 'conversations');
    this.syncDir = path.join(baseDir, '.sync');
    this.indexPath = path.join(baseDir, 'index.json');
    this.dirtyPath = path.join(this.syncDir, 'dirty.json');

    // 选项
    this.syncDebounceMs = options.syncDebounceMs ?? 5000;
    this.copyFilePath = options.copyFilePath || path.join(baseDir, '.sync', 'conversations_full.json');
    this.autoSync = options.autoSync !== false;
    this.cacheMaxSize = options.cacheMaxSize ?? 100;

    /** @type {IndexData|null} */
    this._index = null;

    /** @type {Map<string, ConversationMeta>} id → meta 快速查找 */
    this._metaMap = new Map();

    /** @type {Map<string, object>} id → 完整对话对象缓存（LRU 简化版） */
    this._cache = new Map();

    /** @type {Set<string>} 待同步的对话 ID */
    this._dirtySet = new Set();

    /** @type {NodeJS.Timeout|null} 防抖定时器 */
    this._syncTimer = null;

    /** @type {boolean} 是否正在同步中 */
    this._syncing = false;

    /** @type {Promise<SyncResult>|null} 当前同步操作 */
    this._syncPromise = null;

    /** @type {boolean} index 是否已加载 */
    this._loaded = false;
  }

  // ─── 索引操作 ───────────────────────────────────────────────

  /**
   * 加载索引文件到内存
   * @returns {Promise<IndexData>}
   */
  async loadIndex() {
    try {
      const raw = await fsp.readFile(this.indexPath, 'utf-8');
      this._index = JSON.parse(raw);
    } catch (err) {
      if (err.code === 'ENOENT') {
        // 索引不存在，初始化空索引
        this._index = {
          version: '1.0',
          last_modified: new Date().toISOString(),
          total_conversations: 0,
          conversations: [],
        };
        console.warn(`[ConversationManager] Index not found, initialized empty index.`);
      } else {
        throw new Error(`Failed to load index: ${err.message}`);
      }
    }

    // 建立快速查找映射
    this._metaMap.clear();
    for (const meta of this._index.conversations) {
      this._metaMap.set(meta.id, meta);
    }

    // 加载 dirty 列表
    await this._loadDirtyList();

    this._loaded = true;
    this.emit('indexLoaded', this._index);
    return this._index;
  }

  /**
   * 获取已加载的索引（不重新读磁盘）
   * @returns {IndexData}
   */
  getIndex() {
    this._ensureLoaded();
    return this._index;
  }

  /**
   * 获取对话列表（仅元数据）
   * @param {Object} [options]
   * @param {string}  [options.query]    - 按标题模糊搜索
   * @param {number}  [options.offset=0]
   * @param {number}  [options.limit]
   * @param {'update_time'|'create_time'|'title'} [options.sortBy='update_time']
   * @param {'asc'|'desc'} [options.sortOrder='desc']
   * @returns {ConversationMeta[]}
   */
  listConversations(options = {}) {
    this._ensureLoaded();
    let list = [...this._index.conversations];

    // 搜索过滤
    if (options.query) {
      const q = options.query.toLowerCase();
      list = list.filter((m) => m.title.toLowerCase().includes(q));
    }

    // 排序
    const sortBy = options.sortBy || 'update_time';
    const desc = (options.sortOrder || 'desc') === 'desc';
    list.sort((a, b) => {
      let va = a[sortBy] ?? 0;
      let vb = b[sortBy] ?? 0;
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return desc ? 1 : -1;
      if (va > vb) return desc ? -1 : 1;
      return 0;
    });

    // 分页
    const offset = options.offset || 0;
    if (options.limit != null) {
      list = list.slice(offset, offset + options.limit);
    } else if (offset > 0) {
      list = list.slice(offset);
    }

    return list;
  }

  /**
   * 通过 ID 获取元数据
   * @param {string} id
   * @returns {ConversationMeta|undefined}
   */
  getConversationMeta(id) {
    this._ensureLoaded();
    return this._metaMap.get(id);
  }

  // ─── 单个对话加载 ──────────────────────────────────────────

  /**
   * 按需加载单个对话（优先从缓存读取）
   * @param {string} id - 对话 ID
   * @param {boolean} [forceReload=false] - 是否跳过缓存
   * @returns {Promise<object|null>} 返回完整对话对象（OpenAI 原始结构）
   */
  async loadConversation(id, forceReload = false) {
    this._ensureLoaded();

    // 检查缓存
    if (!forceReload && this._cache.has(id)) {
      // 移到 Map 末尾（简单 LRU）
      const data = this._cache.get(id);
      this._cache.delete(id);
      this._cache.set(id, data);
      return data;
    }

    // 从文件读取
    const filePath = this._convFilePath(id);
    try {
      const raw = await fsp.readFile(filePath, 'utf-8');
      const conv = JSON.parse(raw);

      // 放入缓存
      this._putCache(id, conv);

      return conv;
    } catch (err) {
      if (err.code === 'ENOENT') {
        console.warn(`[ConversationManager] Conversation file not found: ${id}`);
        return null;
      }
      throw new Error(`Failed to load conversation ${id}: ${err.message}`);
    }
  }

  // ─── 保存对话 ──────────────────────────────────────────────

  /**
   * 保存（创建或更新）对话文件，并自动更新索引和 dirty 标记
   * @param {string} id - 对话 ID
   * @param {object} data - 完整对话对象
   * @param {Object} [options]
   * @param {string}  [options.title]  - 覆盖标题（不提供则从 data 中提取）
   * @returns {Promise<void>}
   */
  async saveConversation(id, data, options = {}) {
    this._ensureLoaded();

    // 确保目录存在
    await fsp.mkdir(this.convsDir, { recursive: true });

    // 写对话文件
    const filePath = this._convFilePath(id);
    await fsp.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');

    // 更新缓存
    this._putCache(id, data);

    // 更新索引
    const title = options.title || data.title || 'Untitled';
    const now = Date.now() / 1000;
    const messageCount = this._countMessages(data);

    let meta = this._metaMap.get(id);
    if (meta) {
      meta.title = title;
      meta.update_time = data.update_time ? Number(data.update_time) : now;
      meta.message_count = messageCount;
      meta.dirty = true;
    } else {
      meta = {
        id,
        title,
        create_time: data.create_time ? Number(data.create_time) : now,
        update_time: data.update_time ? Number(data.update_time) : now,
        message_count: messageCount,
        dirty: true,
      };
      this._index.conversations.unshift(meta);
      this._metaMap.set(id, meta);
      this._index.total_conversations = this._index.conversations.length;
    }

    // 标记 dirty
    this._dirtySet.add(id);
    await this._persistIndex();
    await this._persistDirtyList();

    this.emit('conversationSaved', { id, title });

    // 触发自动同步
    if (this.autoSync) {
      this._scheduleSyncDebounced();
    }
  }

  /**
   * 仅更新对话标题（不重写整个对话文件）
   * @param {string} id
   * @param {string} newTitle
   * @returns {Promise<boolean>}
   */
  async updateTitle(id, newTitle) {
    this._ensureLoaded();
    const meta = this._metaMap.get(id);
    if (!meta) return false;

    meta.title = newTitle;
    meta.update_time = Date.now() / 1000;

    // 如果对话已缓存，也更新缓存里的 title
    if (this._cache.has(id)) {
      const conv = this._cache.get(id);
      if (conv) conv.title = newTitle;
    }

    // 更新对话文件中的 title 字段（按需加载）
    const filePath = this._convFilePath(id);
    try {
      const raw = await fsp.readFile(filePath, 'utf-8');
      const conv = JSON.parse(raw);
      conv.title = newTitle;
      conv.update_time = meta.update_time;
      await fsp.writeFile(filePath, JSON.stringify(conv, null, 2), 'utf-8');
    } catch (err) {
      console.warn(`[ConversationManager] Could not update title in file: ${err.message}`);
    }

    await this._persistIndex();
    this.emit('titleUpdated', { id, title: newTitle });
    return true;
  }

  /**
   * 删除对话
   * @param {string} id
   * @returns {Promise<boolean>}
   */
  async deleteConversation(id) {
    this._ensureLoaded();

    // 从索引移除
    const idx = this._index.conversations.findIndex((m) => m.id === id);
    if (idx === -1) return false;

    this._index.conversations.splice(idx, 1);
    this._metaMap.delete(id);
    this._index.total_conversations = this._index.conversations.length;
    this._dirtySet.delete(id);
    this._cache.delete(id);

    // 删除文件
    const filePath = this._convFilePath(id);
    try {
      await fsp.unlink(filePath);
    } catch (err) {
      if (err.code !== 'ENOENT') {
        console.warn(`[ConversationManager] Failed to delete file: ${err.message}`);
      }
    }

    await this._persistIndex();
    await this._persistDirtyList();

    this.emit('conversationDeleted', { id });
    return true;
  }

  // ─── 同步机制 ──────────────────────────────────────────────

  /**
   * 手动触发同步：合并所有 dirty 对话到完整副本文件
   * @returns {Promise<SyncResult>}
   */
  async syncToCopy() {
    // 避免重入
    if (this._syncing && this._syncPromise) {
      return this._syncPromise;
    }

    this._syncing = true;
    this._syncPromise = this._doSync();

    try {
      const result = await this._syncPromise;
      return result;
    } finally {
      this._syncing = false;
      this._syncPromise = null;
    }
  }

  /**
   * 获取 dirty 对话 ID 列表
   * @returns {string[]}
   */
  getDirtyIds() {
    return [...this._dirtySet];
  }

  /**
   * 是否有未同步的更改
   * @returns {boolean}
   */
  hasPendingSync() {
    return this._dirtySet.size > 0;
  }

  /**
   * 清理资源（取消定时器等）
   */
  destroy() {
    if (this._syncTimer) {
      clearTimeout(this._syncTimer);
      this._syncTimer = null;
    }
    this._cache.clear();
    this.removeAllListeners();
  }

  // ─── 内部方法 ──────────────────────────────────────────────

  /** @private */
  _ensureLoaded() {
    if (!this._loaded) {
      throw new Error('ConversationManager: index not loaded. Call loadIndex() first.');
    }
  }

  /** @private */
  _convFilePath(id) {
    return path.join(this.convsDir, `conv_${id}.json`);
  }

  /**
   * 统计对话消息数量
   * @private
   * @param {object} conv
   * @returns {number}
   */
  _countMessages(conv) {
    // 支持 mapping 格式（OpenAI 原始）
    const mapping = conv.mapping;
    if (mapping) {
      let count = 0;
      for (const nodeId in mapping) {
        const node = mapping[nodeId];
        if (node.message) {
          const content = node.message.content;
          if (content && content.content_type === 'text') {
            const parts = content.parts || [];
            if (parts.filter(Boolean).join('').length > 0) count++;
          }
        }
      }
      return count;
    }
    // 支持简单 messages 数组格式
    if (Array.isArray(conv.messages)) {
      return conv.messages.length;
    }
    return 0;
  }

  /**
   * 放入缓存（简单 LRU 淘汰）
   * @private
   */
  _putCache(id, data) {
    if (this._cache.has(id)) {
      this._cache.delete(id);
    }
    this._cache.set(id, data);

    // 淘汰最久未使用
    while (this._cache.size > this.cacheMaxSize) {
      const firstKey = this._cache.keys().next().value;
      this._cache.delete(firstKey);
    }
  }

  /**
   * 持久化索引到磁盘
   * @private
   */
  async _persistIndex() {
    this._index.last_modified = new Date().toISOString();
    await fsp.writeFile(this.indexPath, JSON.stringify(this._index, null, 2), 'utf-8');
  }

  /**
   * 持久化 dirty 列表到磁盘
   * @private
   */
  async _persistDirtyList() {
    await fsp.mkdir(this.syncDir, { recursive: true });
    await fsp.writeFile(this.dirtyPath, JSON.stringify([...this._dirtySet], null, 2), 'utf-8');
  }

  /**
   * 从磁盘加载 dirty 列表
   * @private
   */
  async _loadDirtyList() {
    try {
      const raw = await fsp.readFile(this.dirtyPath, 'utf-8');
      const ids = JSON.parse(raw);
      this._dirtySet = new Set(Array.isArray(ids) ? ids : []);

      // 把 dirty 状态同步到索引元数据
      for (const meta of this._index.conversations) {
        meta.dirty = this._dirtySet.has(meta.id);
      }
    } catch (err) {
      if (err.code !== 'ENOENT') {
        console.warn(`[ConversationManager] Failed to load dirty list: ${err.message}`);
      }
      this._dirtySet = new Set();
    }
  }

  /**
   * 防抖调度同步
   * @private
   */
  _scheduleSyncDebounced() {
    if (this._syncTimer) {
      clearTimeout(this._syncTimer);
    }
    this._syncTimer = setTimeout(async () => {
      this._syncTimer = null;
      try {
        const result = await this.syncToCopy();
        this.emit('syncCompleted', result);
      } catch (err) {
        this.emit('syncError', err);
        console.error(`[ConversationManager] Auto-sync failed: ${err.message}`);
      }
    }, this.syncDebounceMs);
  }

  /**
   * 执行实际同步
   * @private
   * @returns {Promise<SyncResult>}
   */
  async _doSync() {
    const dirtyIds = [...this._dirtySet];
    if (dirtyIds.length === 0) {
      return { success: true, syncedCount: 0, syncedIds: [] };
    }

    this.emit('syncStarted', { count: dirtyIds.length });
    console.log(`[ConversationManager] Syncing ${dirtyIds.length} dirty conversations...`);

    try {
      // 读取或初始化完整副本
      let fullData = [];
      try {
        const raw = await fsp.readFile(this.copyFilePath, 'utf-8');
        fullData = JSON.parse(raw);
        if (!Array.isArray(fullData)) fullData = [];
      } catch (err) {
        if (err.code !== 'ENOENT') {
          console.warn(`[ConversationManager] Could not read copy file, starting fresh: ${err.message}`);
        }
      }

      // 建立 ID → index 映射
      /** @type {Map<string, number>} */
      const idxMap = new Map();
      for (let i = 0; i < fullData.length; i++) {
        const cid = fullData[i].conversation_id || fullData[i].id || '';
        if (cid) idxMap.set(cid, i);
      }

      // 逐个合并 dirty 对话
      for (const id of dirtyIds) {
        const conv = await this.loadConversation(id);
        if (!conv) {
          // 对话已被删除，从副本中也移除
          if (idxMap.has(id)) {
            const removeIdx = idxMap.get(id);
            fullData.splice(removeIdx, 1);
            // 重建索引映射（splice 之后后续索引都变了）
            idxMap.clear();
            for (let i = 0; i < fullData.length; i++) {
              const cid = fullData[i].conversation_id || fullData[i].id || '';
              if (cid) idxMap.set(cid, i);
            }
          }
          continue;
        }

        if (idxMap.has(id)) {
          fullData[idxMap.get(id)] = conv;
        } else {
          fullData.push(conv);
          idxMap.set(id, fullData.length - 1);
        }
      }

      // 写完整副本
      await fsp.mkdir(path.dirname(this.copyFilePath), { recursive: true });
      await fsp.writeFile(this.copyFilePath, JSON.stringify(fullData, null, 2), 'utf-8');

      // 清除 dirty 标记
      for (const id of dirtyIds) {
        this._dirtySet.delete(id);
        const meta = this._metaMap.get(id);
        if (meta) meta.dirty = false;
      }

      await this._persistIndex();
      await this._persistDirtyList();

      console.log(`[ConversationManager] Sync complete: ${dirtyIds.length} conversations merged.`);

      return {
        success: true,
        syncedCount: dirtyIds.length,
        syncedIds: dirtyIds,
      };
    } catch (err) {
      console.error(`[ConversationManager] Sync error: ${err.message}`);
      return {
        success: false,
        syncedCount: 0,
        syncedIds: [],
        error: err.message,
      };
    }
  }
}

module.exports = { ConversationManager };
