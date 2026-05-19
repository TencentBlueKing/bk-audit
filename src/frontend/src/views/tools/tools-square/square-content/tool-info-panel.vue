<!--
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
-->
<template>
  <div class="tool-info-panel">
    <div class="panel-tab">
      <div
        v-bk-tooltips="{ content: '返回工具广场', delay: [300, 0] }"
        class="tab-icon"
        role="button"
        tabindex="0"
        @click="handleGoHome"
        @keydown.enter.prevent="handleGoHome"
        @keydown.space.prevent="handleGoHome">
        <img
          alt="home"
          class="home-icon"
          src="@images/home-tool.svg">
      </div>
      <div class="tab-box">
        <div
          v-for="(item, index) in toolList"
          :key="`${item.uid}-${index}`"
          v-bk-tooltips="{ content: item.name, disabled: !isTabTextOverflow[`${item.uid}-${index}`], delay: [300, 0] }"
          class="panel-tab-item"
          :class="{ active: activeUid === item.uid }"
          @click="handleTabClick(item.uid)"
          @contextmenu.prevent="handleTabContextMenu($event, item, index)">
          <img
            v-if="item.tool_type === 'smart_page'"
            alt="smart_page"
            class="tab-tool-icon"
            :src="userProfileIcon">
          <audit-icon
            v-else
            class="tab-tool-icon"
            svg
            :type="itemIcon(item)" />
          <span
            :ref="(el) => setTabTextRef(`${item.uid}-${index}`, el as HTMLElement)"
            class="tab-text">{{ item.name }}</span>
          <img
            alt="delete"
            class="delete-fill"
            src="@images/delete-circle.svg"
            @click.stop="handleTabClose(item.uid)">
        </div>
        <!-- 新增工具按钮 -->
        <add-tool-popover
          v-if="toolList.length > 0"
          :scene-name-map="props.sceneNameMap"
          :scope-params="props.scopeParams"
          :tags-enums="tagsEnums"
          :tool-list="toolList"
          @add-tool="(tool) => emit('addTool', tool)"
          @switch-tool="(tool) => emit('switchTab', tool.uid)" />
      </div>
    </div>
    <!-- 右键菜单 -->
    <teleport to="body">
      <div
        v-show="contextMenu.visible"
        ref="contextMenuRef"
        class="tab-context-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }">
        <div
          class="context-menu-item"
          @click="handleContextCopy">
          复制工具
        </div>
        <div
          class="context-menu-item"
          @click="handleContextRename">
          重命名标签
        </div>
        <div class="context-menu-divider" />
        <div
          class="context-menu-item"
          @click="handleContextCloseCurrent">
          关闭当前
        </div>
        <div
          class="context-menu-item"
          @click="handleContextCloseAll">
          关闭所有
        </div>
      </div>
    </teleport>
    <!-- 重命名弹窗 -->
    <bk-dialog
      v-model:is-show="renameDialog.visible"
      title="重命名"
      width="480"
      @confirm="handleRenameConfirm">
      <div class="rename-form">
        <div class="rename-label">
          标签名称 <span class="rename-required">*</span>
        </div>
        <bk-input
          v-model="renameDialog.value"
          placeholder="请输入标签名称" />
      </div>
    </bk-dialog>
    <div class="panel-content">
      <template
        v-for="tool in toolList"
        :key="tool.uid">
        <!-- smart_page 类型工具（如审计用户画像） -->
        <audit-user-profile
          v-if="tool.tool_type === 'smart_page'"
          v-show="activeUid === tool.uid"
          :tool-config="toolDetailMap[tool.uid]?.config"
          :tool-uid="tool.uid"
          @open-game-detail="handleOpenGameDetail" />
        <!-- 游戏数据详情 -->
        <game-detail
          v-else-if="tool.uid.startsWith('game_detail_')"
          v-show="activeUid === tool.uid"
          :game-data="gameDetailDataMap[tool.uid]"
          :initial-tab="gameDetailInitialTabMap[tool.uid]"
          :tool-uid="gameDetailToolUidMap[tool.uid]" />
        <!-- 普通工具 -->
        <tool-content
          v-else-if="toolDetailMap[tool.uid]"
          v-show="activeUid === tool.uid"
          :ref="(el: any) => setToolContentRef(tool.uid, el)"
          :content-style="{ height: '100%' }"
          :get-tool-name-and-type="getToolNameAndType"

          :search-list="getSearchList(tool.uid)"
          :tool-details="toolDetailMap[tool.uid]"
          :uid="tool.uid"
          @open-field-down="handleOpenFieldDown"
          @update:search-list="(val) => setSearchList(tool.uid, val)" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useRouter } from 'vue-router';

  import { InfoBox } from 'bkui-vue';

  import ToolManageService from '@service/tool-manage';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';
  import ToolInfo from '@model/tool/tool-info';

  import AuditUserProfile from '../components/audit-profile/audit-user-profile.vue';
  import GameDetail from '../components/game/game-detail.vue';
  import ToolContent from '../components/tool-content.vue';

  import AddToolPopover from './add-tool-popover.vue';

  import useRequest from '@/hooks/use-request';
  import useToolTabs from '@/hooks/use-tool-tabs';
  import userProfileIcon from '@/images/user.svg';

  interface SearchItem {
    value: any;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
    choices: Array<{
      key: string;
      name: string;
    }>;
    disabled: boolean;
    is_show?: boolean;
  }

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  interface Props {
    toolList: ToolInfo[];
    activeUid: string;
    tagsEnums: TagItem[];
    // eslint-disable-next-line vue/no-unused-properties
    scopeParams?: {
      scope_type?: string;
      scope_id?: string;
    };
    // eslint-disable-next-line vue/no-unused-properties
    sceneNameMap?: Record<number, string>;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<{
    close: [];
    goHome: [];
    closeTab: [uid: string];
    switchTab: [uid: string];
    addTool: [tool: ToolInfo];
  }>();

  const router = useRouter();

  const {
    getDrillDownParams,
    clearDrillDownParams,
  } = useToolTabs();


  const tabTextRefs = ref<Record<string, HTMLElement | null>>({});
  const isTabTextOverflow = ref<Record<string, boolean>>({});

  const setTabTextRef = (key: string, el: HTMLElement | null) => {
    if (el) {
      tabTextRefs.value[key] = el;
    }
  };

  const checkTabTextOverflow = () => {
    const result: Record<string, boolean> = {};
    Object.entries(tabTextRefs.value).forEach(([key, el]) => {
      if (el) {
        result[key] = el.scrollWidth > el.clientWidth;
      }
    });
    isTabTextOverflow.value = result;
  };
  let resizeObserver: ResizeObserver | null = null;

  onMounted(() => {
    resizeObserver = new ResizeObserver(() => {
      checkTabTextOverflow();
    });
    const tabBox = document.querySelector('.tab-box');
    if (tabBox) {
      resizeObserver.observe(tabBox);
    }
    document.addEventListener('click', handleDocumentClick);
  });

  onBeforeUnmount(() => {
    resizeObserver?.disconnect();
    document.removeEventListener('click', handleDocumentClick);
  });

  watch(
    () => props.toolList,
    () => {
      nextTick(() => {
        checkTabTextOverflow();
      });
    },
    { deep: true },
  );

  const handleGoHome = () => emit('goHome');
  const handleTabClick = (uid: string) => emit('switchTab', uid);
  const handleTabClose = (uid: string) => emit('closeTab', uid);

  // 右键菜单相关
  const contextMenuRef = ref<HTMLElement | null>(null);
  const contextMenu = ref({
    visible: false,
    x: 0,
    y: 0,
    tool: null as ToolInfo | null,
    index: 0,
  });

  // 重命名弹窗
  const renameDialog = ref({
    visible: false,
    value: '',
    tool: null as ToolInfo | null,
  });

  // 关闭所有确认弹窗（使用 InfoBox）
  const handleContextCloseAll = () => {
    hideContextMenu();
    InfoBox({
      title: '确认关闭所有工具？',
      subTitle: '关闭后将返回工具广场',
      confirmText: '关闭',
      cancelText: '取消',
      headerAlign: 'center' as any,
      contentAlign: 'center' as any,
      confirmButtonTheme: 'danger' as any,
      onConfirm: () => {
        emit('close');
      },
    });
  };

  const hideContextMenu = () => {
    contextMenu.value.visible = false;
  };

  const handleTabContextMenu = (e: MouseEvent, tool: ToolInfo, index: number) => {
    contextMenu.value = {
      visible: true,
      x: e.clientX,
      y: e.clientY,
      tool,
      index,
    };
  };

  // 复制工具 - 在右侧新增一个tab展示该工具副本
  // 存储复制工具的原始uid映射：copyUid -> originalUid
  const copyUidMap = ref<Record<string, string>>({});

  const handleContextCopy = () => {
    const { tool } = contextMenu.value;
    if (!tool) return;
    // 计算副本编号
    const baseName = tool.name.replace(/\(\d+\)$/, '').trim();
    let maxNum = 1;
    props.toolList.forEach((t) => {
      const match = t.name.match(new RegExp(`^${baseName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\((\\d+)\\)$`));
      if (match) {
        const num = parseInt(match[1], 10);
        if (num >= maxNum) maxNum = num + 1;
      }
    });
    const newName = `${baseName}(${maxNum})`;
    const copyUid = `${tool.uid}_copy_${Date.now()}`;
    // 记录映射：获取原始 uid（如果本身也是 copy，追溯到源头）
    const originalUid = copyUidMap.value[tool.uid] || tool.uid;
    copyUidMap.value[copyUid] = originalUid;
    const dupTool = new ToolInfo({
      ...tool,
      uid: copyUid,
      name: newName,
    } as any);
    emit('addTool', dupTool);
    hideContextMenu();
  };

  // 重命名标签
  const handleContextRename = () => {
    const { tool } = contextMenu.value;
    if (!tool) return;
    renameDialog.value = {
      visible: true,
      value: tool.name,
      tool,
    };
    hideContextMenu();
  };

  const handleRenameConfirm = () => {
    const { tool } = renameDialog.value;
    if (!tool || !renameDialog.value.value.trim()) return;
    // 直接修改 toolList 中对应的 name
    const target = props.toolList.find(t => t.uid === tool.uid);
    if (target) {
      target.name = renameDialog.value.value.trim();
    }
    renameDialog.value.visible = false;
  };

  // 关闭当前
  const handleContextCloseCurrent = () => {
    const { tool } = contextMenu.value;
    if (!tool) return;
    emit('closeTab', tool.uid);
    hideContextMenu();
  };

  // 点击其他区域关闭右键菜单
  const handleDocumentClick = (e: MouseEvent) => {
    if (contextMenuRef.value && !contextMenuRef.value.contains(e.target as Node)) {
      hideContextMenu();
    }
  };

  const itemIcon = (item: { tool_type?: string }) => {
    switch (item.tool_type) {
    case 'data_search':
      return 'sqlxiao';
    case 'bk_vision':
      return 'bkvisonxiao';
    case 'api':
      return 'apixiao';
    case 'smart_page':
      return 'user';
    case 'game_detail':
      return 'apixiao';
    default:
      return 'apixiao';
    }
  };

  const toolContentRefs = ref<Record<string, any>>({});
  // 从 sessionStorage 恢复用户输入值映射（精简存储：只存 raw_name → value）
  const STORAGE_KEY_SEARCH_VALUES = 'tool_tabs_search_values_map';
  const loadSearchValuesMap = (): Record<string, Record<string, any>> => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY_SEARCH_VALUES);
      if (raw) return JSON.parse(raw);
      // 兼容迁移：从旧的完整存储格式中提取 value
      const oldRaw = sessionStorage.getItem('tool_tabs_search_list_map');
      if (oldRaw) {
        const oldMap = JSON.parse(oldRaw) as Record<string, Array<{ raw_name: string; value: any }>>;
        const migrated: Record<string, Record<string, any>> = {};
        Object.entries(oldMap).forEach(([uid, list]) => {
          const valuesObj: Record<string, any> = {};
          list.forEach((item) => {
            valuesObj[item.raw_name] = item.value;
          });
          migrated[uid] = valuesObj;
        });
        // 存储迁移后的精简数据并清理旧 key
        sessionStorage.setItem(STORAGE_KEY_SEARCH_VALUES, JSON.stringify(migrated));
        sessionStorage.removeItem('tool_tabs_search_list_map');
        return migrated;
      }
      return {};
    } catch {
      return {};
    }
  };
  // 精简存储：{ [uid]: { [raw_name]: value } }
  const searchValuesMap = ref<Record<string, Record<string, any>>>(loadSearchValuesMap());
  // 运行时完整 searchList（不持久化，由工具详情 + 存储的 value 合并生成）
  const searchListMap = ref<Record<string, SearchItem[]>>({});

  const syncSearchValuesToStorage = () => {
    try {
      sessionStorage.setItem(STORAGE_KEY_SEARCH_VALUES, JSON.stringify(searchValuesMap.value));
    } catch {
      // 静默处理
    }
  };
  // 从完整 searchList 提取用户输入值并同步到 sessionStorage
  const syncSearchListToStorage = () => {
    Object.entries(searchListMap.value).forEach(([uid, list]) => {
      const valuesObj: Record<string, any> = {};
      list.forEach((item) => {
        valuesObj[item.raw_name] = item.value;
      });
      searchValuesMap.value[uid] = valuesObj;
    });
    syncSearchValuesToStorage();
  };
  const toolDetailMap = ref<Record<string, ToolDetailModel>>({});
  const {
    data: allToolsData,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    manual: true,
  });

  const setToolContentRef = (uid: string, el: any) => {
    if (el) {
      toolContentRefs.value[uid] = el;
    }
  };

  const getSearchList = (uid: string): SearchItem[] => searchListMap.value[uid] || [];
  const setSearchList = (uid: string, val: SearchItem[]) => {
    searchListMap.value[uid] = val;
    syncSearchListToStorage();
  };

  // 记录当前正在请求详情的激活 uid（用于复制工具时区分原始uid和副本uid）
  const pendingActiveUid = ref<string>('');

  // 获取工具详情
  const {
    run: fetchToolDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      toolDetailMap.value[data.uid] = data;
      // 对于复制的工具，也将详情映射到 copy uid 下
      Object.entries(copyUidMap.value).forEach(([copyUid, originalUid]) => {
        if (originalUid === data.uid && !toolDetailMap.value[copyUid]) {
          toolDetailMap.value[copyUid] = data;
        }
      });
      const toolInList = props.toolList.find(t => t.uid === data.uid);
      if (toolInList && toolInList.name === data.uid && data.name) {
        toolInList.name = data.name;
        toolInList.tool_type = data.tool_type;
        toolInList.description = data.description;
        toolInList.tags = data.tags || [];
        toolInList.strategies = data.strategies || [];
      }
      // 如果是复制工具触发的请求，用 copyUid 作为 key 来初始化
      const currentActiveUid = pendingActiveUid.value;
      if (currentActiveUid && copyUidMap.value[currentActiveUid]) {
        toolDetailMap.value[currentActiveUid] = data;
        applyToolDetail(data, currentActiveUid);
      } else {
        applyToolDetail(data);
      }
    },
  });

  const extractDataByPath = (data: any, path: string): any => {
    if (!path || !data) return null;
    const cleanPath = path.replace(/\[\d+\]/g, '');
    const pathParts = cleanPath.split('.').filter(part => part.length > 0);
    let result = data;
    for (const part of pathParts) {
      if (result === null || result === undefined) return null;
      result = result[part];
    }
    if (typeof result === 'string') {
      result = result.replace(/^["']|["']$/g, '');
    }
    return result;
  };

  const checkRequiredFieldsFilled = (searchList: SearchItem[]): boolean => {
    if (!searchList || searchList.length === 0) return false;
    const requiredFields = searchList.filter(item => item.required);
    if (requiredFields.length === 0) return false;
    return requiredFields.every((item) => {
      if (Array.isArray(item.value)) {
        return item.value.length > 0;
      }
      return item.value !== null && item.value !== undefined && item.value !== '';
    });
  };

  const applyToolDetail = (data: ToolDetailModel, overrideUid?: string) => {
    const uid = overrideUid || data.uid;
    // 检查是否有下钻参数
    const drillParams = getDrillDownParams(uid);

    if (data.tool_type !== 'bk_vision') {
      const createSearchItem = (item: any) => ({
        ...item,
        value: item.default_value || (item.field_category === 'person_select' || item.field_category === 'time_range_select' ? [] : null),
        required: item.required,
        disabled: false,
      });

      if (drillParams) {
        // 下钻模式：根据 drill_config 自动填充参数
        const configMap = new Map<string, any>();
        drillParams.drillConfig.forEach((configItem) => {
          configMap.set(configItem.source_field, configItem);
        });

        searchListMap.value[uid] = (data.config?.input_variable || []).map((item: any) => {
          const searchItem = createSearchItem(item);
          const configItem = configMap.get(searchItem.raw_name);
          if (!configItem) return searchItem;

          let dynamicValue: any = '';
          if (configItem.target_value_type !== 'fixed_value') {
            if (configItem.target_value.includes('.')) {
              dynamicValue = extractDataByPath(drillParams.rowData, configItem.target_value);
            } else if (configItem.target_field_type === 'basic' || !configItem.target_field_type) {
              dynamicValue = drillParams.rowData?.[configItem.target_value] ?? searchItem.value;
            } else {
              dynamicValue = drillParams.rowData?.event_data?.[configItem.target_value] ?? searchItem.value;
            }
          }

          return {
            ...searchItem,
            value: configItem.target_value_type === 'fixed_value'
              ? configItem.target_value
              : dynamicValue,
          };
        });
        syncSearchListToStorage();

        // 清除下钻参数，避免重复使用
        clearDrillDownParams(uid);
      } else if (!searchListMap.value[uid]) {
        // 非下钻：从工具配置构建完整 searchList，并尝试恢复缓存的用户输入值
        const cachedValues = searchValuesMap.value[uid];
        searchListMap.value[uid] = (data.config?.input_variable || []).map((item: any) => {
          const searchItem = createSearchItem(item);
          // 如果有缓存的用户输入值，优先使用缓存值
          if (cachedValues && cachedValues[searchItem.raw_name] !== undefined) {
            searchItem.value = cachedValues[searchItem.raw_name];
          }
          return searchItem;
        });
        syncSearchListToStorage();
      }

      nextTick(() => {
        const ref = toolContentRefs.value[uid];
        if (ref) {
          ref.setFormItemData(searchListMap.value[uid]);
          const shouldAutoSubmit = drillParams || checkRequiredFieldsFilled(searchListMap.value[uid]);
          if (shouldAutoSubmit) {
            nextTick(() => {
              ref.submit();
            });
          }
        }
      });
    } else {
      nextTick(() => {
        const ref = toolContentRefs.value[uid];
        if (ref) {
          ref.executeBkVision();
        }
      });
    }
    if (data.tool_type === 'smart_page') {
      return;
    }
  };

  const getToolNameAndType = (uid: string): { name: string; type: string } => {
    const tool = props.toolList.find(item => item.uid === uid);
    if (tool) {
      return {
        name: tool.name || '',
        type: tool.tool_type || '',
      };
    }
    const allTool = allToolsData.value?.find((item: ToolDetailModel) => item.uid === uid);
    return {
      name: allTool?.name || '',
      type: allTool?.tool_type || '',
    };
  };

  // 游戏详情数据缓存（从 sessionStorage 恢复）
  const STORAGE_KEY_GAME_DETAIL = 'tool_tabs_game_detail_map';
  const loadGameDetailCache = () => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY_GAME_DETAIL);
      return raw ? JSON.parse(raw) : { data: {}, tab: {}, toolUid: {} };
    } catch {
      return { data: {}, tab: {}, toolUid: {} };
    }
  };
  const savedGameCache = loadGameDetailCache();
  const gameDetailDataMap = ref<Record<string, any>>(savedGameCache.data);
  // 游戏详情初始 tab 缓存
  const gameDetailInitialTabMap = ref<Record<string, string>>(savedGameCache.tab);
  // 游戏详情对应的 smart_page 工具 uid 缓存
  const gameDetailToolUidMap = ref<Record<string, string>>(savedGameCache.toolUid);

  const syncGameDetailToStorage = () => {
    try {
      sessionStorage.setItem(STORAGE_KEY_GAME_DETAIL, JSON.stringify({
        data: gameDetailDataMap.value,
        tab: gameDetailInitialTabMap.value,
        toolUid: gameDetailToolUidMap.value,
      }));
    } catch {
      // 静默处理
    }
  };

  // 打开游戏数据详情
  const handleOpenGameDetail = (gameData: Record<string, any>, initialTab?: string) => {
    const gameUid = `game_detail_${gameData.openid || ''}_${gameData.name}`;
    // 缓存游戏数据（保留 gameid 用于子接口查询）
    gameDetailDataMap.value[gameUid] = {
      name: gameData.name,
      openid: gameData.openid || '',
      gameid: gameData.gameid || '',
      ctx: gameData.ctx || '',
      wechat: gameData.wechat || '',
      coinBalance: gameData.coinBalance || 0,
      totalRecharge: gameData.totalRecharge || 0,
      totalGift: gameData.totalGift || 0,
      totalIssue: gameData.totalIssue || 0,
    };
    // 找到 smart_page 工具的 uid，传递给 game-detail 用于接口调用
    const smartPageTool = props.toolList.find(t => t.tool_type === 'smart_page');
    if (smartPageTool) {
      gameDetailToolUidMap.value[gameUid] = smartPageTool.uid;
    }
    // 缓存初始 tab
    gameDetailInitialTabMap.value[gameUid] = initialTab || 'overview';
    // 构造一个 ToolInfo 实例用于 tab 展示
    const gameTool = new ToolInfo({
      uid: gameUid,
      name: `${gameData.ctx || ''} - ${gameData.name}`,
      version: 1,
      tool_type: 'game_detail',
      description: '',
      namespace: '',
      is_bkvision: false,
      favorite: false,
      strategies: [],
      tags: [],
      created_by: '',
      created_at: '',
      updated_by: '',
      updated_at: '',
    } as any);
    emit('addTool', gameTool);
    // 切换到新 tab
    emit('switchTab', gameUid);
    // 同步游戏详情缓存到 sessionStorage
    syncGameDetailToStorage();
  };

  // 处理下钻事件：在新浏览器标签页中打开目标工具
  const handleOpenFieldDown = (
    drillDownItem: OutputFields,
    drillDownItemRowData: Record<string, any>,
    activeUid?: string,
  ) => {
    const targetUid = activeUid || drillDownItem.drill_config[0]?.tool.uid;
    if (!targetUid) return;

    // 获取对应的 drill_config
    const drillConfig = drillDownItem.drill_config.find(c => c.tool.uid === targetUid)?.config || [];

    try {
      Object.keys(sessionStorage)
        .filter(key => key.startsWith('drill_'))
        .forEach(key => sessionStorage.removeItem(key));
    } catch {
      // 静默处理
    }

    const drillKey = `drill_${Date.now()}_${Math.random().toString(36)
      .slice(2, 10)}`;
    try {
      sessionStorage.setItem(drillKey, JSON.stringify({
        drillConfig,
        rowData: drillDownItemRowData,
      }));
    } catch {
      // sessionStorage 写入失败时静默处理
    }

    const routeData = router.resolve({
      name: 'toolDetail',
      params: { uid: targetUid },
      query: {
        drillKey,
      },
    });

    window.open(routeData.href, '_blank');
  };

  // 监听激活工具变化，仅在未加载过时请求详情
  watch(
    () => props.activeUid,
    (newUid) => {
      if (!newUid) return;
      // 跳过游戏详情等固定工具
      if (newUid.startsWith('game_detail_')) return;
      const drillParams = getDrillDownParams(newUid);
      // 如果该工具详情尚未加载，或者有下钻参数需要重新填充，则请求
      if (!toolDetailMap.value[newUid] || drillParams) {
        // 对于复制的工具，使用原始uid来获取详情
        const realUid = copyUidMap.value[newUid] || newUid;
        pendingActiveUid.value = newUid;
        fetchToolDetail({ uid: realUid });
      }
      // 已加载的工具无需任何操作，v-show 会自动切换显示
    },
    { immediate: true },
  );

  // smart_page（审计用户画像）查询状态在 sessionStorage 中按 toolUid 区分存储的 key 前缀
  // 关闭工具 tab 时清理对应 key，避免下次打开时仍恢复上次输入
  const STORAGE_KEY_PROFILE_QUERY_PREFIX = 'tool_audit_profile_query_';

  // 监听工具列表变化，清理已关闭工具的缓存数据
  watch(
    () => props.toolList,
    (newList) => {
      const activeUids = new Set(newList.map(t => t.uid));
      // 清理不在列表中的工具缓存
      Object.keys(toolDetailMap.value).forEach((uid) => {
        if (!activeUids.has(uid)) {
          delete toolDetailMap.value[uid];
          delete searchListMap.value[uid];
          delete searchValuesMap.value[uid];
          delete toolContentRefs.value[uid];
        }
      });
      // 清理不在列表中的游戏详情缓存
      Object.keys(gameDetailDataMap.value).forEach((uid) => {
        if (!activeUids.has(uid)) {
          delete gameDetailDataMap.value[uid];
          delete gameDetailInitialTabMap.value[uid];
          delete gameDetailToolUidMap.value[uid];
        }
      });
      // 清理已关闭的 smart_page 工具在 sessionStorage 中保存的查询输入
      try {
        Object.keys(sessionStorage)
          .filter(key => key.startsWith(STORAGE_KEY_PROFILE_QUERY_PREFIX))
          .forEach((key) => {
            const uid = key.slice(STORAGE_KEY_PROFILE_QUERY_PREFIX.length);
            if (uid && !activeUids.has(uid)) {
              sessionStorage.removeItem(key);
            }
          });
      } catch {
        // 静默处理
      }
      syncSearchValuesToStorage();
      syncGameDetailToStorage();
    },
    { deep: true },
  );
</script>

<style scoped lang="postcss">
.tool-info-panel {
  width: 100%;
  height: 100%;
  background: #f5f7fa;
}

.panel-tab {
  display: grid;
  grid-template-columns: 50px minmax(0, 1fr);
  align-items: center;
  height: 52px;
  overflow: visible;
  background: #fff;
  border-bottom: 1px solid #dcdee5;
}

.tab-box {
  display: flex;
  height: 100%;
  min-width: 0;
  padding-right: 4px;
  overflow: hidden;
  white-space: nowrap;
  align-items: center;
}

.tab-icon {
  display: flex;
  width: 100%;
  height: 100%;
  color: #979ba5;
  cursor: pointer;
  background-color: #fafbfd;
  border-right: 1px solid #dcdee5;
  transition: all .15s;
  align-items: center;
  justify-content: center;
}

.tab-icon:hover {
  color: #3a84ff;
  background: #f0f1f5;
}

.home-icon {
  display: block;
  width: 21px;
  height: 24px;
  cursor: pointer;
}

.panel-tab-item {
  position: relative;
  display: flex;
  height: 100%;
  max-width: 280px;
  min-width: 40px;
  padding: 0 8px;
  cursor: pointer;
  background: #fafbfd;
  border-right: 1px solid #dcdee5;
  transition: all .15s;
  align-items: center;
  flex: 1 1 auto;
  gap: 4px;

}

.panel-tab-item:hover {
  background: #f0f1f5;
}


.panel-tab-item:hover .delete-fill {
  opacity: 100%;
}

.tab-tool-icon {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
}

.panel-tab-item.active {
  background: #fff;
}

.panel-tab-item.active .tab-text {
  font-weight: 500;
  color: #3a84ff;
}

.panel-tab-item.active .delete-fill {
  opacity: 100%;
}

.tab-text {
  flex: 1;
  overflow: hidden;
  font-size: 14px;
  color: #63656e;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color .15s;
}

.delete-fill {
  display: block;
  width: 15px;
  height: 15px;
  margin-left: 4px;
  cursor: pointer;
  opacity: 0%;
  transition: all .15s;
  flex: 0 0 auto;
}

.delete-fill:hover {
  opacity: 100%;
  filter: brightness(.8);
}

.panel-content {
  height: calc(100% - 52px);
  padding: 16px 24px;
  overflow: auto;
  background: #f5f7fa;
  scrollbar-width: thin;
  scrollbar-color: #dcdee5 transparent;
}

.panel-content::-webkit-scrollbar {
  width: 4px;
}

.panel-content::-webkit-scrollbar-track {
  background: transparent;
}

.panel-content::-webkit-scrollbar-thumb {
  background: #dcdee5;
  border-radius: 999px;
}

.panel-content::-webkit-scrollbar-thumb:hover {
  background: #c4c6cc;
}

.rename-form {
  padding: 8px 0;
}

.rename-label {
  margin-bottom: 8px;
  font-size: 14px;
  color: #313238;
}

.rename-required {
  color: #ea3636;
}

</style>

<style lang="postcss">
.tab-context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 80px;
  padding: 4px 0;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgb(0 0 0 / 15%);
}

.tab-context-menu .context-menu-divider {
  height: 1px;
  margin: 4px 0;
  background: #dcdee5;
}

.tab-context-menu .context-menu-item {
  padding: 8px 16px;
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
  cursor: pointer;
  transition: background .15s;
}

.tab-context-menu .context-menu-item:hover {
  color: #3a84ff;
  background: #f0f5ff;
}
</style>
