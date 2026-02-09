/**
 * 使用示例 — ConversationManager
 *
 * 前提：conversations.json 已通过后端上传接口自动拆分
 *
 * 运行方式:  node example.js
 */

const path = require('path');
const { ConversationManager } = require('./ConversationManager');

// Development path — matches Python backend's SPLIT_DIR
const SPLIT_DIR = path.resolve(__dirname, '../../backend/data/conversations_split');

async function main() {
  console.log('=== ConversationManager 使用示例 ===\n');

  // ━━━ 1. 初始化 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  const manager = new ConversationManager(SPLIT_DIR, {
    syncDebounceMs: 5000,   // 5 秒防抖
    autoSync: true,         // 保存后自动同步
    cacheMaxSize: 50,       // 缓存 50 条对话
  });

  // 监听事件
  manager.on('indexLoaded', (index) => {
    console.log(`[Event] 索引加载完毕，共 ${index.total_conversations} 条对话`);
  });
  manager.on('conversationSaved', ({ id, title }) => {
    console.log(`[Event] 对话已保存: ${id} — "${title}"`);
  });
  manager.on('syncStarted', ({ count }) => {
    console.log(`[Event] 开始同步 ${count} 条 dirty 对话...`);
  });
  manager.on('syncCompleted', (result) => {
    console.log(`[Event] 同步完成: ${result.syncedCount} 条已合并`);
  });

  // ━━━ 2. 加载索引 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  const index = await manager.loadIndex();
  console.log(`\n总对话数: ${index.total_conversations}`);
  console.log(`索引版本: ${index.version}`);
  console.log(`最后修改: ${index.last_modified}\n`);

  // ━━━ 3. 列表查询 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // 获取最近 5 条对话
  const recent = manager.listConversations({ limit: 5 });
  console.log('--- 最近 5 条对话 ---');
  for (const meta of recent) {
    const date = meta.update_time ? new Date(meta.update_time * 1000).toLocaleDateString() : 'N/A';
    console.log(`  [${meta.id.substring(0, 8)}...] ${meta.title}  (${meta.message_count} 条消息, ${date})`);
  }

  // 搜索
  const searchResults = manager.listConversations({ query: 'AI', limit: 3 });
  console.log(`\n--- 搜索 "AI" 的前 3 条 ---`);
  for (const meta of searchResults) {
    console.log(`  [${meta.id.substring(0, 8)}...] ${meta.title}`);
  }

  // ━━━ 4. 按需加载对话详情 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  if (recent.length > 0) {
    const firstId = recent[0].id;
    console.log(`\n--- 加载对话详情: ${firstId} ---`);

    const conv = await manager.loadConversation(firstId);
    if (conv) {
      console.log(`  标题: ${conv.title}`);
      const mapping = conv.mapping || {};
      const nodeCount = Object.keys(mapping).length;
      console.log(`  mapping 节点数: ${nodeCount}`);
    }

    // 第二次加载会命中缓存（瞬间返回）
    console.log(`  再次加载（缓存命中）...`);
    const t0 = Date.now();
    await manager.loadConversation(firstId);
    console.log(`  耗时: ${Date.now() - t0}ms`);
  }

  // ━━━ 5. 保存对话示例 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  const testId = `test_${Date.now()}`;
  const testConv = {
    conversation_id: testId,
    title: '测试对话 — ConversationManager',
    create_time: Date.now() / 1000,
    update_time: Date.now() / 1000,
    mapping: {
      root: {
        id: 'root',
        message: null,
        parent: null,
        children: ['msg1'],
      },
      msg1: {
        id: 'msg1',
        message: {
          id: 'msg1',
          author: { role: 'user', name: null, metadata: {} },
          content: { content_type: 'text', parts: ['你好，这是一条测试消息'] },
          create_time: Date.now() / 1000,
        },
        parent: 'root',
        children: ['msg2'],
      },
      msg2: {
        id: 'msg2',
        message: {
          id: 'msg2',
          author: { role: 'assistant', name: null, metadata: {} },
          content: { content_type: 'text', parts: ['你好！很高兴见到你。'] },
          create_time: Date.now() / 1000 + 1,
        },
        parent: 'msg1',
        children: [],
      },
    },
  };

  console.log(`\n--- 保存测试对话: ${testId} ---`);
  await manager.saveConversation(testId, testConv);
  console.log(`  已保存。dirty 列表: [${manager.getDirtyIds().join(', ')}]`);

  // ━━━ 6. 手动触发同步 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  console.log(`\n--- 手动同步 ---`);
  const syncResult = await manager.syncToCopy();
  console.log(`  同步结果: ${JSON.stringify(syncResult)}`);

  // ━━━ 7. 清理测试数据 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  console.log(`\n--- 删除测试对话 ---`);
  const deleted = await manager.deleteConversation(testId);
  console.log(`  删除: ${deleted}`);

  // ━━━ 8. 销毁 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  manager.destroy();
  console.log(`\n=== 示例结束 ===`);
}

main().catch((err) => {
  console.error('Error:', err);
  process.exit(1);
});
