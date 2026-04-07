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
          <audit-icon
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
          :tags-enums="tagsEnums"
          :tool-list="toolList"
          @add-tool="(tool) => emit('addTool', tool)" />
      </div>
    </div>
    <div class="panel-content">
      <div class="content-header">
        <div class="top-right">
          <audit-icon
            class="top-left-icon"
            svg
            :type="activeTool ? itemIcon(activeTool) : ''" />
          <div class="top-right-box">
            <div class="top-right-title">
              <span class="top-right-name">{{ activeTool?.name || '' }}</span>
              <bk-tag
                v-for="(tag, tagIndex) in (activeTool?.tags || []).slice(0, 3)"
                :key="tagIndex"
                class="desc-tag">
                {{ returnTagsName(tag) }}
              </bk-tag>
              <bk-tag
                v-if="activeTool?.tags && activeTool.tags.length > 3"
                v-bk-tooltips="{
                  content: tagContent(activeTool.tags),
                  placement: 'top',
                }"
                class="desc-tag">
                + {{ activeTool.tags.length - 3 }}
              </bk-tag>
              <bk-tag
                class="desc-tag desc-tag-info"
                theme="info"
                @click.stop="handlesStrategiesClick(activeTool)">
                运用在 {{ activeTool?.strategies?.length || 0 }} 个策略中
              </bk-tag>
            </div>
            <div class="top-right-desc">
              {{ activeTool?.description || '--' }}
            </div>
          </div>
        </div>
      </div>
      <template
        v-for="tool in toolList"
        :key="tool.uid">
        <tool-content
          v-if="toolDetailMap[tool.uid]"
          v-show="activeUid === tool.uid"
          :ref="(el: any) => setToolContentRef(tool.uid, el)"
          :content-style="{ height: 'calc(100% - 160px)' }"
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
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';
  import ToolInfo from '@model/tool/tool-info';

  import ToolContent from '../components/tool-content.vue';

  import AddToolPopover from './add-tool-popover.vue';

  import useRequest from '@/hooks/use-request';
  import useToolTabs from '@/hooks/use-tool-tabs';

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

  // 工具类型 → 图标映射
  const TOOL_ICON_MAP: Record<string, string> = {
    data_search: 'sqlxiao',
    bk_vision: 'bkvisonxiao',
    api: 'apixiao',
  };
  const itemIcon = (item: { tool_type?: string }) => TOOL_ICON_MAP[item.tool_type || ''] || 'apixiao';

  const activeTool = computed(() => props.toolList.find(t => t.uid === props.activeUid) || null);

  const returnTagsName = (tagId: string) => {
    let tagName = '';
    props.tagsEnums.forEach((item: TagItem) => {
      if (item.tag_id === tagId) {
        tagName = item.tag_name;
      }
    });
    return tagName;
  };
  const tagContent = (tags: Array<string>) => {
    const tagNameList = props.tagsEnums.map((i: TagItem) => {
      if (tags.slice(3, tags.length).includes(i.tag_id)) {
        return i.tag_name;
      }
      return null;
    }).filter(e => e !== null);
    return tagNameList.join(',');
  };

  // 策略跳转
  const handlesStrategiesClick = (item: ToolInfo | null) => {
    if (!item?.strategies || item.strategies.length === 0) {
      return;
    }
    const url = router.resolve({
      name: 'strategyList',
      query: {
        strategy_id: item.strategies.join(','),
      },
    }).href;
    window.open(url, '_blank');
  };

  const toolContentRefs = ref<Record<string, any>>({});
  const searchListMap = ref<Record<string, SearchItem[]>>({});
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

        // 清除下钻参数，避免重复使用
        clearDrillDownParams(uid);
      } else if (!searchListMap.value[uid]) {
        // 非下钻：仅在该工具尚未初始化搜索列表时才设置
        searchListMap.value[uid] = (data.config?.input_variable || []).map(createSearchItem);
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

    // 构建路由
    const routeData = router.resolve({
      name: 'toolDetail',
      params: { uid: targetUid },
      query: {
        drillConfig: encodeURIComponent(JSON.stringify(drillConfig)),
        rowData: encodeURIComponent(JSON.stringify(drillDownItemRowData)),
      },
    });

    window.open(routeData.href, '_blank');
  };

  // 监听激活工具变化，仅在未加载过时请求详情
  watch(
    () => props.activeUid,
    (newUid) => {
      if (!newUid) return;
      const drillParams = getDrillDownParams(newUid);
      // 如果该工具详情尚未加载，或者有下钻参数需要重新填充，则请求
      if (!toolDetailMap.value[newUid] || drillParams) {
        fetchToolDetail({ uid: newUid });
      }
      // 已加载的工具无需任何操作，v-show 会自动切换显示
    },
    { immediate: true },
  );

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

  &:nth-child(2) {
    border-left: 1px solid #dcdee5;
  }
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

.content-header {
  padding: 8px 0 16px;
  border-radius: 8px;
}

.top-right {
  display: flex;
  gap: 12px;
  align-items: flex-start;

  .top-left-icon {
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
  }

  .top-right-box {
    flex: 1;
    min-width: 0;

    .top-right-title {
      display: flex;
      gap: 6px;
      align-items: center;
      margin-bottom: 8px;
      flex-wrap: wrap;

      .top-right-name {
        max-width: 800px;
        overflow: hidden;
        font-size: 16px;
        font-weight: 700;
        line-height: 24px;
        color: #313238;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .desc-tag {
        font-size: 12px;
        font-weight: 500;
        line-height: 22px;
        color: #4d4f56;
        border-radius: 2px;
      }

      .desc-tag-info {
        color: #3a84ff;
        cursor: pointer;
        background: #f0f5ff;

        &:hover {
          color: #1768ef;
          background: #e1ecff;
        }
      }
    }

    .top-right-desc {
      font-size: 14px;
      line-height: 22px;
      color: #63656e;
      word-break: break-word;
    }
  }
}

</style>
