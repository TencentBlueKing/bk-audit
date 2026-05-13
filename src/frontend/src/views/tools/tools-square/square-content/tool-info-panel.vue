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
    <div class="panel-header">
      <span class="title-text">工具详情</span>
      <div
        class="header-close"
        @click="handleClose">
        <audit-icon type="close" />
      </div>
    </div>
    <div class="panel-tab">
      <div
        class="tab-icon"
        role="button"
        tabindex="0"
        @click="handleGoHome"
        @keydown.enter.prevent="handleGoHome"
        @keydown.space.prevent="handleGoHome">
        <img
          alt="home"
          class="home-icon"
          src="@images/home.svg">
      </div>
      <div class="tab-box">
        <div
          v-for="(item, index) in toolList"
          :key="`${item.uid}-${index}`"
          v-bk-tooltips="{ content: item.name, disabled: !isTabTextOverflow[`${item.uid}-${index}`], delay: [300, 0] }"
          class="panel-tab-item"
          :class="{ active: activeUid === item.uid }"
          @click="handleTabClick(item.uid)">
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
          :scope-params="props.scopeParams"
          :tags-enums="tagsEnums"
          :tool-list="toolList"
          @add-tool="(tool) => emit('addTool', tool)" />
      </div>
    </div>
    <div class="panel-content">
      <template
        v-for="tool in toolList"
        :key="tool.uid">
        <!-- smart_page 类型工具（如审计用户画像） -->
        <audit-user-profile
          v-if="tool.tool_type === 'smart_page'"
          v-show="activeUid === tool.uid"
          :tool-config="toolDetailMap[tool.uid]?.config"
          :tool-name="tool.name"
          :tool-uid="tool.uid"
          @open-game-detail="handleOpenGameDetail" />
        <!-- 游戏数据详情 -->
        <game-detail
          v-else-if="tool.uid.startsWith('game_detail_')"
          v-show="activeUid === tool.uid"
          :game-data="gameDetailDataMap[tool.uid]"
          :initial-tab="gameDetailInitialTabMap[tool.uid]"
          :tool-name="tool.name"
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
          :uid="toolDetailMap[tool.uid].uid"
          @open-field-down="handleOpenFieldDown"
          @update:search-list="(val) => setSearchList(tool.uid, val)" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useRouter } from 'vue-router';

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
  });

  onBeforeUnmount(() => {
    resizeObserver?.disconnect();
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

  const handleClose = () => emit('close');
  const handleGoHome = () => emit('goHome');
  const handleTabClick = (uid: string) => emit('switchTab', uid);
  const handleTabClose = (uid: string) => emit('closeTab', uid);

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
  // 从 sessionStorage 恢复 searchListMap
  const STORAGE_KEY_SEARCH_LIST = 'tool_tabs_search_list_map';
  const loadSearchListMap = (): Record<string, SearchItem[]> => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY_SEARCH_LIST);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  };
  const searchListMap = ref<Record<string, SearchItem[]>>(loadSearchListMap());
  const syncSearchListToStorage = () => {
    try {
      sessionStorage.setItem(STORAGE_KEY_SEARCH_LIST, JSON.stringify(searchListMap.value));
    } catch {
      // 静默处理
    }
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

  // 获取工具详情
  const {
    run: fetchToolDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      toolDetailMap.value[data.uid] = data;
      const toolInList = props.toolList.find(t => t.uid === data.uid);
      if (toolInList && toolInList.name === data.uid && data.name) {
        toolInList.name = data.name;
        toolInList.tool_type = data.tool_type;
        toolInList.description = data.description;
        toolInList.tags = data.tags || [];
        toolInList.strategies = data.strategies || [];
      }
      applyToolDetail(data);
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

  const applyToolDetail = (data: ToolDetailModel) => {
    const { uid } = data;
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
        // 非下钻：仅在该工具尚未初始化搜索列表时才设置
        searchListMap.value[uid] = (data.config?.input_variable || []).map(createSearchItem);
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
        fetchToolDetail({ uid: newUid });
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
      syncSearchListToStorage();
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

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #dcdee5;
}

.title-text {
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
  color: #313238;
}

.header-close {
  width: 24px;
  height: 24px;
  font-size: 16px;
  line-height: 24px;
  color: #979ba5;
  text-align: center;
  cursor: pointer;
  border-radius: 50%;
  transition: all .15s;
  user-select: none;
  flex: 0 0 auto;
}

.header-close:hover {
  color: #63656e;
  background: #f0f1f5;
}

.panel-tab {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  align-items: center;
  height: 42px;
  padding: 0 12px 0 8px;
  overflow: hidden;
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
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: #979ba5;
  cursor: pointer;
  border-radius: 4px;
  transition: all .15s;
}

.tab-icon:hover {
  color: #3a84ff;
  background: #f0f5ff;
}

.home-icon {
  display: block;
  width: 16px;
  height: 16px;
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
  height: calc(100% - 86px);
  padding: 24px;
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

</style>
