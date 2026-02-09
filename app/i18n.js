// i18n.js - 国际化支持模块

class I18n {
  constructor() {
    this.currentLanguage = 'zh'; // 默认语言为中文
    this.translations = {};
    this.supportedLanguages = ['en', 'zh'];
  }

  // 初始化 - 加载翻译文件
  async init() {
    try {
      // 从 localStorage 读取保存的语言选择，否则使用默认语言
      const savedLanguage = localStorage.getItem('selectedLanguage');
      if (savedLanguage && this.supportedLanguages.includes(savedLanguage)) {
        this.currentLanguage = savedLanguage;
      }

      // 加载所有语言文件
      for (const lang of this.supportedLanguages) {
        try {
          // 修复路径：从 renderer 目录向上一级，然后进入 locales 目录
          const filePath = `../locales/${lang}.json`;
          console.log('[I18N] Loading:', filePath);
          
          const response = await fetch(filePath);
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          
          const data = await response.json();
          this.translations[lang] = data;
          console.log('[I18N] Loaded', lang, 'successfully with keys:', Object.keys(data).length);
        } catch (error) {
          console.error(`Failed to load language file for ${lang}:`, error);
          console.warn('[I18N] Trying alternative path...');
          
          // Try alternative path
          try {
            const altPath = `./locales/${lang}.json`;
            console.log('[I18N] Trying alternative path:', altPath);
            const response = await fetch(altPath);
            if (response.ok) {
              const data = await response.json();
              this.translations[lang] = data;
              console.log('[I18N] Loaded from alternative path:', lang);
            }
          } catch (altError) {
            console.error('[I18N] Alternative path also failed:', altError);
          }
        }
      }

      // 检查翻译是否加载成功
      console.log('[I18N] Translations loaded:', Object.keys(this.translations));
      for (const lang in this.translations) {
        console.log(`[I18N] ${lang} keys:`, Object.keys(this.translations[lang]));
      }

      // 应用当前语言
      this.applyLanguage(this.currentLanguage);
      console.log('[I18N] Initialized with language:', this.currentLanguage);
    } catch (error) {
      console.error('Failed to initialize i18n:', error);
    }
  }

  // 获取翻译文本
  t(key) {
    if (!key) return '';
    
    const keys = key.split('.');
    let value = this.translations[this.currentLanguage];

    if (!value) {
      console.warn(`[I18N] No translations loaded for language: ${this.currentLanguage}`);
      return key;
    }

    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k];
      } else {
        console.warn(`[I18N] Translation key not found: ${key} (language: ${this.currentLanguage})`);
        return key; // 返回 key 作为备用
      }
    }

    return value || key;
  }

  // 设置语言并应用翻译
  setLanguage(lang) {
    if (!this.supportedLanguages.includes(lang)) {
      console.warn(`[I18N] Language not supported: ${lang}`);
      return;
    }

    if (this.currentLanguage === lang) {
      console.log(`[I18N] Language already set to: ${lang}`);
      return;
    }

    this.currentLanguage = lang;
    localStorage.setItem('selectedLanguage', lang);
    
    console.log('[I18N] Setting language to:', lang);
    
    // 完全重新应用翻译
    this.applyLanguage(lang);
    
    // 触发自定义事件，允许其他代码监听语言变化
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
    
    console.log('[I18N] Language changed event fired');
  }

  // 获取当前语言
  getLanguage() {
    return this.currentLanguage;
  }

  // 应用翻译到 DOM
  applyLanguage(lang) {
    // 更新所有带有 data-i18n 属性的元素
    const elements = document.querySelectorAll('[data-i18n]');
    
    elements.forEach(el => {
      const key = el.getAttribute('data-i18n');
      const text = this.t(key);
      
      // 根据元素类型和属性设置文本或占位符
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        if (el.hasAttribute('data-i18n-placeholder')) {
          el.placeholder = text;
        } else {
          el.placeholder = text;
        }
      } else if (el.tagName === 'OPTION') {
        el.textContent = text;
      } else {
        el.textContent = text;
      }
    });

    // 更新所有带有 data-i18n-title 属性的元素
    const titleElements = document.querySelectorAll('[data-i18n-title]');
    titleElements.forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const text = this.t(key);
      el.title = text;
    });

    // 更新语言选择器本身
    const langSelector = document.getElementById('language-select');
    if (langSelector) {
      // Save current value
      const currentValue = langSelector.value;
      // Reset value to force browser to re-render the select display
      langSelector.value = '';
      // Then set to new language
      langSelector.value = lang;
      
      console.log('[I18N] Language selector updated from', currentValue, 'to', lang);
    }

    // 更新 HTML lang 属性
    document.documentElement.lang = lang;
    
    console.log('[I18N] Language changed to:', lang);
  }

  // 批量更新文本（用于动态生成的内容）
  updateElement(element, key) {
    const text = this.t(key);
    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
      element.placeholder = text;
    } else {
      element.textContent = text;
    }
  }

  // 动态翻译某个 HTML 字符串
  translateHTML(html) {
    const temp = document.createElement('div');
    temp.innerHTML = html;
    this.applyLanguage(this.currentLanguage);
    return temp.innerHTML;
  }
}

// 创建全局实例（挂载到 window 上，确保内联脚本可通过 window.i18n 访问）
window.i18n = new I18n();

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', async () => {
  await window.i18n.init();
});
