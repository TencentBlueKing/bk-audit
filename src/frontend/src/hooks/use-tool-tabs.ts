/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/
import { computed, ref } from 'vue';

import ToolInfo from '@model/tool/tool-info';

// 下钻参数接口
export interface DrillDownParams {
  drillConfig: Array<{
    source_field: string;
    target_value_type: string;
    target_value: string;
    target_field_type?: string;
  }>;
  rowData: Record<string, any>;
}

// sessionStorage 存储键
const STORAGE_KEY_TOOLS = 'tool_tabs_opened_tools';
const STORAGE_KEY_ACTIVE = 'tool_tabs_active_uid';

// 从 sessionStorage 恢复已打开的工具列表
const loadOpenedTools = (): ToolInfo[] => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY_TOOLS);
    if (!raw) return [];
    const list = JSON.parse(raw) as ToolInfo[];
    // 用 ToolInfo 构造函数还原为类实例
    return list.map(item => new ToolInfo(item));
  } catch {
    return [];
  }
};

// 从 sessionStorage 恢复当前激活的工具 uid
const loadActiveToolUid = (): string => sessionStorage.getItem(STORAGE_KEY_ACTIVE) || '';

// 将状态同步写入 sessionStorage（新标签页有独立的 sessionStorage，正常写入即可）
const syncToStorage = (tools: ToolInfo[], activeUid: string) => {
  try {
    sessionStorage.setItem(STORAGE_KEY_TOOLS, JSON.stringify(tools));
    sessionStorage.setItem(STORAGE_KEY_ACTIVE, activeUid);
  } catch {
    // sessionStorage 写入失败时静默处理
  }
};

// 模块级别的状态，从 sessionStorage 恢复初始值
const openedTools = ref<ToolInfo[]>(loadOpenedTools());
const activeToolUid = ref(loadActiveToolUid());

// 下钻参数存储（按工具 uid 索引，模块级别共享）
const drillDownParamsMap = ref<Record<string, DrillDownParams>>({});

export default function useToolTabs() {
  // 是否有打开的工具（用于判断是否显示详情面板）
  const hasOpenedTools = computed(() => openedTools.value.length > 0 && activeToolUid.value !== '');

  // 打开工具 - 堆叠到 tab 列表
  const openTool = (tool: ToolInfo, switchToNew = true) => {
    const exists = openedTools.value.some(t => t.uid === tool.uid);
    if (!exists) {
      openedTools.value.push(tool);
    }
    if (switchToNew) {
      activeToolUid.value = tool.uid;
    }
    syncToStorage(openedTools.value, activeToolUid.value);
  };

  // 关闭单个 tab
  const closeTab = (uid: string) => {
    const index = openedTools.value.findIndex(t => t.uid === uid);
    if (index === -1) return;

    openedTools.value.splice(index, 1);

    // 如果关闭的是当前激活的 tab
    if (activeToolUid.value === uid) {
      if (openedTools.value.length > 0) {
        // 切换到相邻 tab
        const newIndex = Math.min(index, openedTools.value.length - 1);
        activeToolUid.value = openedTools.value[newIndex].uid;
      } else {
        // 没有打开的工具了
        activeToolUid.value = '';
      }
    }
    syncToStorage(openedTools.value, activeToolUid.value);
  };

  // 切换 tab
  const switchTab = (uid: string) => {
    activeToolUid.value = uid;
    syncToStorage(openedTools.value, activeToolUid.value);
  };

  // 回到工具广场（不清空 tab 列表，保留状态）
  const goHome = () => {
    activeToolUid.value = '';
    syncToStorage(openedTools.value, activeToolUid.value);
  };

  // 清空所有 tab
  const clearAll = () => {
    openedTools.value = [];
    activeToolUid.value = '';
    syncToStorage(openedTools.value, activeToolUid.value);
  };

  return {
    openedTools,
    activeToolUid,
    hasOpenedTools,
    openTool,
    closeTab,
    switchTab,
    goHome,
    clearAll,
    setDrillDownParams: (uid: string, params: DrillDownParams) => {
      drillDownParamsMap.value[uid] = params;
    },
    getDrillDownParams: (uid: string): DrillDownParams | undefined => drillDownParamsMap.value[uid],
    clearDrillDownParams: (uid: string) => {
      delete drillDownParamsMap.value[uid];
    },
    // 为下钻模式重置状态：清空从原标签页继承的 sessionStorage 数据，后续正常写入新标签页自己的数据
    resetForDrillDown: () => {
      openedTools.value = [];
      activeToolUid.value = '';
      // 清空从原标签页继承的 sessionStorage 数据
      try {
        sessionStorage.removeItem(STORAGE_KEY_TOOLS);
        sessionStorage.removeItem(STORAGE_KEY_ACTIVE);
      } catch {
        // 静默处理
      }
    },
  };
}
