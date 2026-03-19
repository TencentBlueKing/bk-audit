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
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useRoute } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';

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
  padding: 0 12px 0 8px;
  background: #fff;
  border-bottom: 1px solid #dcdee5;
}


.title-text {
  font-size: 14px;
  line-height: 22px;
  color: #313238;
}

.header-close {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  font-size: 14px;
  line-height: 20px;
  color: #979ba5;
  text-align: center;
  cursor: pointer;
  user-select: none;
}

.header-close:hover {
  color: #63656e;
}

.panel-tab {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 28px;
  align-items: center;
  height: 42px;
  padding: 0 8px 0 4px;
  overflow: hidden;
  background: #fafbfd;
  border-bottom: 1px solid #dcdee5;
}

.tab-box {
  display: flex;
  height: 100%;
  min-width: 0;
  padding-right: 4px;
  overflow: auto hidden;
  white-space: nowrap;
  align-items: center;
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: #c4c6cc #f0f1f5;
}

.tab-box::-webkit-scrollbar {
  height: 6px;
}

.tab-box::-webkit-scrollbar-track {
  background: #f0f1f5;
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
  width: 28px;
  height: 22px;
  color: #979ba5;
  cursor: pointer;
}

.tab-icon-add {
  position: relative;
  z-index: 2;
  background: #fafbfd;
  border-left: 1px solid #e6e8ee;
}

.add-icon {
  display: block;
  width: 14px;
  height: 14px;
  cursor: pointer;
}

.home-icon {
  display: block;
  width: 14px;
  height: 14px;
  cursor: pointer;
}

.panel-tab-item {
  display: flex;
  height: 32px;
  max-width: 280px;
  min-width: 140px;
  padding-right: 5px;
  padding-left: 5px;
  cursor: pointer;
  background: #fafbfd;
  border: 1px solid #e2e6ed;
  border-radius: 2px;
  align-items: center;
  flex: 0 0 auto;
}

.tab-tool-icon {
  flex: 0 0 auto;
  width: 14px;
  height: 14px;
  padding-right: 5px;
}

.panel-tab-item.active {
  background: #fff;
  border-color: #c4c6cc;
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
  color: #4d4f56;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-fill {
  margin-left: 5px;
  color: #979ba5;
  flex: 0 0 auto;
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
  height: calc(100% - 78px);
  padding: 12px;
  overflow: auto;
  background: #f5f7fa;
}

.content-header {
  padding: 8px 0 16px;
  border-bottom: 1px solid #dcdee5;
}

.top-right {
  display: flex;
  gap: 8px;
  align-items: flex-start;

  .top-left-icon {
    width: 40px;
    height: 40px;
  }

  .top-right-box {
    flex: 1;
    min-width: 0;

    .top-right-title {
      display: flex;
      gap: 4px;
      align-items: center;
      margin-bottom: 8px;

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
      }

      .desc-tag-info {
        color: #1768ef;
      }
    }

    .top-right-desc {
      font-size: 14px;
      line-height: 22px;
      color: #313238;
      word-break: break-word;
    }
  }
}

</style>
