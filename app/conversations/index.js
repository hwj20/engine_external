/**
 * conversations/ 模块入口
 *
 * The splitting of conversations.json is now handled automatically by the
 * Python backend on upload.  This module exposes the ConversationManager
 * for direct file-level access from the Electron main process if needed.
 *
 * @example
 *   const { ConversationManager } = require('./conversations');
 */

const { ConversationManager } = require('./ConversationManager');

module.exports = {
  ConversationManager,
};
