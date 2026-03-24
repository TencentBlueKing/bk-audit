<template>
  <div class="tool-info-panel">
    <div class="panel-header">
      <span class="title-text">工具详情</span>
      <div
        class="header-close"
        @click="handleClose">
        x
      </div>
    </div>
    <div class="panel-tab">
      <div
        class="tab-icon"
        role="button"
        tabindex="0"
        @click="handleClose"
        @keydown.enter.prevent="handleClose"
        @keydown.space.prevent="handleClose">
        <img
          alt="home"
          class="home-icon"
          src="@images/home.svg">
      </div>
      <div class="tab-box">
        <div
          v-for="(item, index) in toolList"
          :key="`${item.uid}-${index}`"
          class="panel-tab-item"
          :class="{ active: activeIndex === index }"
          @click="handleTabClick(index, $event)">
          <audit-icon
            class="tab-tool-icon"
            svg
            :type="itemIcon(item)" />
          <span class="tab-text">{{ item.name }}</span>
          <audit-icon
            v-if="activeIndex === index"
            class="delete-fill"
            type="delete-fill"
            @click.stop />
        </div>
      </div>
      <div class="tab-icon tab-icon-add">
        <audit-icon
          class="add-icon"
          type="add" />
        <span
          v-if="toolList.length > 0"
          class="add-badge">
          +{{ toolList.length }}
        </span>
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
      <!-- 工具内容区域 -->
      <tool-content
        v-if="activeToolDetail"
        ref="toolContentRef"
        :content-style="{ height: 'calc(100% - 160px)' }"
        :get-tool-name-and-type="getToolNameAndType"
        :search-list="searchList"
        :tool-details="activeToolDetail"
        :uid="activeToolDetail.uid"
        @update:search-list="(val) => searchList = val" />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue';
  import { useRoute } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';
  import ToolInfo from '@model/tool/tool-info';

  import ToolContent from '../components/tool-content.vue';

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

  interface Props {
    toolInfo: ToolInfo | null;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<{
    close: [];
  }>();
  const route = useRoute();
  const activeIndex = ref(0);
  const toolList = ref<Array<{
    uid: string;
    name: string;
    description: string;
    tool_type?: string;
    tags?: string[];
    strategies?: string[];
  }>>([]);

  const handleClose = () => {
    emit('close');
  };
  const handleTabClick = (index: number, event: MouseEvent) => {
    activeIndex.value = index;
    const target = event.currentTarget as HTMLElement | null;
    target?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'center',
    });
  };

  const normalizeTool = (tool: any, fallbackUid = '') => ({
    uid: tool?.uid || fallbackUid,
    name: tool?.name || fallbackUid || '未命名工具',
    description: tool?.description || '',
    tool_type: tool?.tool_type,
    tags: tool?.tags || [],
    strategies: tool?.strategies || [],
  });

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

  const fetchToolListByUrl = async () => {
    const toolIdParam = route.query.tool_id;
    const toolIds = typeof toolIdParam === 'string'
      ? toolIdParam.split(',').map(id => id.trim())
        .filter(Boolean)
      : [];

    if (toolIds.length === 0) {
      toolList.value = props.toolInfo ? [normalizeTool(props.toolInfo, props.toolInfo.uid)] : [];
      activeIndex.value = 0;
      return;
    }

    const uniqueIds = Array.from(new Set(toolIds));
    const detailList = await Promise.all(uniqueIds.map(async (uid) => {
      try {
        const detail = await ToolManageService.fetchToolsDetail({ uid });
        return normalizeTool(detail, uid);
      } catch (error) {
        return normalizeTool(null, uid);
      }
    }));

    toolList.value = detailList;
    const currentUid = props.toolInfo?.uid;
    const matchedIndex = currentUid
      ? detailList.findIndex(item => item.uid === currentUid)
      : -1;
    activeIndex.value = matchedIndex >= 0 ? matchedIndex : 0;
  };

  const activeTool = computed(() => toolList.value[activeIndex.value] || null);

  const toolContentRef = ref();
  const searchList = ref<SearchItem[]>([]);
  const activeToolDetail = ref<ToolDetailModel | null>(null);

  // 获取工具详情
  const {
    run: fetchToolDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      activeToolDetail.value = data;
      // 构建搜索列表
      if (data.tool_type !== 'bk_vision') {
        searchList.value = (data.config?.input_variable || []).map((item: any) => ({
          ...item,
          value: item.default_value || (item.field_category === 'person_select' || item.field_category === 'time_range_select' ? [] : null),
          required: item.required,
          disabled: false,
        }));
        nextTick(() => {
          if (toolContentRef.value) {
            toolContentRef.value.setFormItemData(searchList.value);
          }
        });
      } else {
        nextTick(() => {
          if (toolContentRef.value) {
            toolContentRef.value.executeBkVision();
          }
        });
      }
    },
  });

  const getToolNameAndType = (uid: string): { name: string; type: string } => {
    const tool = toolList.value.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type || '',
    } : {
      name: '',
      type: '',
    };
  };

  // 监听激活工具变化，获取详情
  watch(
    () => activeTool.value?.uid,
    (newUid) => {
      if (newUid) {
        activeToolDetail.value = null;
        fetchToolDetail({ uid: newUid });
      }
    },
  );

  watch(
    () => [route.query.tool_id, props.toolInfo?.uid],
    () => {
      fetchToolListByUrl();
    },
    { immediate: true },
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
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: center;
  height: 42px;
  padding: 0 12px 0 8px;
  overflow: hidden;
  background: #fff;
  border-bottom: 1px solid #dcdee5;
}

.tab-box {
  display: flex;
  gap: 4px;
  height: 100%;
  min-width: 0;
  padding-right: 4px;
  overflow: auto hidden;
  white-space: nowrap;
  align-items: center;
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: #c4c6cc transparent;
}

.tab-box::-webkit-scrollbar {
  height: 4px;
}

.tab-box::-webkit-scrollbar-track {
  background: transparent;
}

.tab-box::-webkit-scrollbar-thumb {
  background: #c4c6cc;
  border-radius: 999px;
}

.tab-box::-webkit-scrollbar-thumb:hover {
  background: #aeb3bd;
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

.tab-icon-add {
  position: relative;
  z-index: 2;
  width: auto;
  min-width: 32px;
  padding: 0 4px;
  background: transparent;
  border-left: none;
}

.add-icon {
  display: block;
  width: 14px;
  height: 14px;
  color: #3a84ff;
  cursor: pointer;
}

.add-badge {
  display: inline-flex;
  height: 18px;
  min-width: 18px;
  padding: 0 4px;
  margin-left: 2px;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  color: #fff;
  background: #3a84ff;
  border-radius: 9px;
  align-items: center;
  justify-content: center;
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
  height: 32px;
  max-width: 280px;
  min-width: 120px;
  padding: 0 8px;
  cursor: pointer;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  transition: all .15s;
  align-items: center;
  flex: 0 0 auto;
  gap: 4px;
}

.panel-tab-item:hover {
  color: #3a84ff;
}

.panel-tab-item:hover .tab-text {
  color: #3a84ff;
}

.tab-tool-icon {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
}

.panel-tab-item.active .tab-text {
  font-weight: 500;
  color: #3a84ff;
}


.tab-dot {
  flex: 0 0 auto;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.tab-text {
  flex: 1;
  overflow: hidden;
  font-size: 12px;
  color: #63656e;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color .15s;
}

.delete-fill {
  margin-left: 4px;
  font-size: 14px;
  color: #c4c6cc;
  transition: color .15s;
  flex: 0 0 auto;
}

.delete-fill:hover {
  color: #979ba5;
}

.tab-close {
  flex: 0 0 auto;
  width: 14px;
  height: 14px;
  font-size: 12px;
  line-height: 14px;
  color: #979ba5;
  text-align: center;
}

.panel-content {
  height: calc(100% - 86px);
  padding: 16px;
  overflow: auto;
  background: #f5f7fa;
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
        max-width: 220px;
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
