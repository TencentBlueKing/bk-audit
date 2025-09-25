import type { Settings } from 'bkui-vue/lib/table/props';
import { computed } from 'vue';

/**
 * 表格设置类型定义
 */
export interface TableField {
  label: string;
  field: string;
  disabled: boolean;
}

export interface TableSettings extends Settings {
  fields: TableField[];
  checked: string[];
  showLineHeight?: boolean;
  trigger: 'manual';
  [key: string]: any;
}

/**
 * 表格设置合并 Hook
 * @param storageKey 本地存储的 key
 * @param defaultSettings 默认设置
 * @returns 合并后的设置
 */
export default function useTableSettings(storageKey: string, defaultSettings: () => TableSettings) {
  const settings = computed(() => {
    const latestDefaultSettings = defaultSettings(); // 获取最新的默认配置
    const jsonStr = localStorage.getItem(storageKey);

    if (!jsonStr) return latestDefaultSettings;

    try {
      const savedSettings = JSON.parse(jsonStr);

      // 字段配置：完全以代码中的定义为准，直接使用 latestDefaultSettings.fields
      // 选中的字段合并：保留用户选择 + 新增的默认选中字段
      const savedCheckedSet = new Set(savedSettings.checked || []);
      const newDefaultChecked = latestDefaultSettings.checked
        .filter(field => !savedCheckedSet.has(field)); // 找出新增的默认选中字段
      const mergedChecked = [...(savedSettings.checked || []), ...newDefaultChecked]
        .filter(field => latestDefaultSettings.fields.some(f => f.field === field)); // 过滤无效字段

      return {
        ...latestDefaultSettings,       // 保留最新默认配置的其他属性
        checked: mergedChecked,         // 合并后的选中字段
        showLineHeight: false,          // 强制重置行高设置
        trigger: 'manual' as const,     // 添加 as const 类型断言
      };
    } catch (e) {
      console.error(`本地设置解析失败，使用默认配置: ${storageKey}`, e);
      return latestDefaultSettings;
    }
  });

  return {
    settings,
  };
}
