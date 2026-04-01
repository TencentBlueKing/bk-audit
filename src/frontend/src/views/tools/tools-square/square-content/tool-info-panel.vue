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
                {{ tag }}
              </bk-tag>
              <bk-tag
                v-if="activeTool?.tags && activeTool.tags.length > 3"
                class="desc-tag">
                + {{ activeTool.tags.length - 3 }}
              </bk-tag>
              <bk-tag
                class="desc-tag desc-tag-info"
                theme="info">
                运用在 {{ activeTool?.strategies?.length || 0 }} 个策略中
              </bk-tag>
            </div>
            <div class="top-right-desc">
              {{ activeTool?.description || '--' }}
            </div>
          </div>
        </div>
      </div>
      <!-- 工具内容区域 - 为每个打开的工具渲染独立实例，用 v-show 保留状态 -->
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
          @update:search-list="(val) => setSearchList(tool.uid, val)" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';
  import ToolInfo from '@model/tool/tool-info';

  import ToolContent from '../components/tool-content.vue';

  import AddToolPopover from './add-tool-popover.vue';

  import useRequest from '@/hooks/use-request';

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


  // ========== Tab 文本溢出检测 ==========
  const tabTextRefs = ref<Record<string, HTMLElement | null>>({});
  const isTabTextOverflow = ref<Record<string, boolean>>({});

  const setTabTextRef = (key: string, el: HTMLElement | null) => {
    if (el) {
      tabTextRefs.value[key] = el;
    }
  };

  // 检测所有 tab 文本是否溢出
  const checkTabTextOverflow = () => {
    const result: Record<string, boolean> = {};
    Object.entries(tabTextRefs.value).forEach(([key, el]) => {
      if (el) {
        result[key] = el.scrollWidth > el.clientWidth;
      }
    });
    isTabTextOverflow.value = result;
  };

  // 监听窗口大小变化，重新检测溢出
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

  // 工具列表变化时重新检测溢出
  watch(
    () => props.toolList,
    () => {
      nextTick(() => {
        checkTabTextOverflow();
      });
    },
    { deep: true },
  );

  // 关闭整个面板
  const handleClose = () => {
    emit('close');
  };

  // 点击首页图标，回到工具列表（不清除已打开的 tab）
  const handleGoHome = () => {
    emit('goHome');
  };

  // 点击 tab 切换工具
  const handleTabClick = (uid: string) => {
    emit('switchTab', uid);
  };

  // 关闭单个 tab
  const handleTabClose = (uid: string) => {
    emit('closeTab', uid);
  };

  const itemIcon = (item: { tool_type?: string }) => {
    switch (item.tool_type) {
    case 'data_search':
      return 'sqlxiao';
    case 'bk_vision':
      return 'bkvisonxiao';
    case 'api':
      return 'apixiao';
    default:
      return 'apixiao';
    }
  };

  // 当前激活的工具
  const activeTool = computed(() => props.toolList.find(t => t.uid === props.activeUid) || null);

  // 每个工具独立的 ref 引用和搜索列表
  const toolContentRefs = ref<Record<string, any>>({});
  const searchListMap = ref<Record<string, SearchItem[]>>({});

  // 缓存已加载的工具详情，同时作为渲染数据源
  const toolDetailMap = ref<Record<string, ToolDetailModel>>({});

  // 设置/获取每个工具的 tool-content ref
  const setToolContentRef = (uid: string, el: any) => {
    if (el) {
      toolContentRefs.value[uid] = el;
    }
  };

  // 获取指定工具的搜索列表
  const getSearchList = (uid: string): SearchItem[] => searchListMap.value[uid] || [];

  // 设置指定工具的搜索列表
  const setSearchList = (uid: string, val: SearchItem[]) => {
    searchListMap.value[uid] = val;
  };

  // 获取工具详情
  const {
    run: fetchToolDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      // 存入详情 map，触发对应工具的 v-if 渲染
      toolDetailMap.value[data.uid] = data;
      // 初始化该工具的搜索列表和表单
      applyToolDetail(data);
    },
  });

  // 应用工具详情到视图（初始化搜索列表和表单）
  const applyToolDetail = (data: ToolDetailModel) => {
    const { uid } = data;
    if (data.tool_type !== 'bk_vision') {
      // 仅在该工具尚未初始化搜索列表时才设置（避免切换 tab 时覆盖已有数据）
      if (!searchListMap.value[uid]) {
        searchListMap.value[uid] = (data.config?.input_variable || []).map((item: any) => ({
          ...item,
          value: item.default_value || (item.field_category === 'person_select' || item.field_category === 'time_range_select' ? [] : null),
          required: item.required,
          disabled: false,
        }));
      }
      nextTick(() => {
        const ref = toolContentRefs.value[uid];
        if (ref) {
          ref.setFormItemData(searchListMap.value[uid]);
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
    return tool ? {
      name: tool.name,
      type: tool.tool_type || '',
    } : {
      name: '',
      type: '',
    };
  };

  // 监听激活工具变化，仅在未加载过时请求详情
  watch(
    () => props.activeUid,
    (newUid) => {
      if (!newUid) return;
      // 如果该工具详情尚未加载，则请求
      if (!toolDetailMap.value[newUid]) {
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
        background: #f0f5ff;
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
