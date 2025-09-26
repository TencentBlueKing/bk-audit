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
      // 选中的字段合并：disabled字段强制checked，非disabled字段以用户本地设置为主
      const savedCheckedSet = new Set(savedSettings.checked || []);

      // 获取所有字段的选中状态
      const mergedChecked = latestDefaultSettings.fields
        .map((field) => {
          // disabled字段：强制为checked（以代码为准）
          if (field.disabled) {
            return field.field;
          }
          // 非disabled字段：以用户本地设置为主
          return savedCheckedSet.has(field.field) ? field.field : null;
        })
        .filter(field => field !== null); // 过滤掉null值

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
