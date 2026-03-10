<template>
  <div>
    <audit-sideslider
      v-model:isShow="show"
      :quick-close="false"
      :show-footer="isEditing"
      show-footer-slot
      show-header-slot
      title=""
      :width="drawerWidth">
      <template #header>
        <div class="ai-report-header">
          <div class="ai-report-title-wrapper">
            <span class="ai-report-title-text">{{ headerTitle }}</span>
          </div>
          <div
            v-if="!isEditing"
            class="ai-report-header-actions">
            <bk-button
              class="mr8"
              @click="handleEdit">
              {{ t('编辑') }}
            </bk-button>
            <bk-dropdown trigger="click">
              <bk-button theme="primary">
                <audit-icon
                  class="mr4"
                  type="download" />
                {{ t('导出报告') }}
              </bk-button>
              <template #content>
                <bk-dropdown-menu>
                  <bk-dropdown-item @click="handleExport('pdf')">
                    {{ t('导出为 PDF') }}
                  </bk-dropdown-item>
                  <bk-dropdown-item @click="handleExport('markdown')">
                    {{ t('导出为 Markdown') }}
                  </bk-dropdown-item>
                </bk-dropdown-menu>
              </template>
            </bk-dropdown>
            <audit-icon
              v-bk-tooltips="isFullscreen ? t('退出全屏') : t('全屏')"
              class="ai-report-fullscreen-icon ml8"
              :type="isFullscreen ? 'un-full-screen-2' : 'full-screen'"
              @click="handleToggleFullscreen" />
          </div>
        </div>
      </template>
      <div class="ai-report-preview-body">
        <template v-if="!isEditing">
          <div
            v-if="metaList.length"
            class="ai-report-meta">
            <div class="ai-report-meta-row">
              <div
                v-for="item in metaList"
                :key="item.key"
                class="ai-report-meta-item">
                <div class="label">
                  {{ item.label }}
                </div>
                <div class="value">
                  {{ item.value }}
                </div>
              </div>
            </div>
          </div>

          <div class="ai-report-section">
            <div class="ai-report-section-header">
              <img
                class="ai-report-section-icon"
                src="@images/ai-icon.svg">
              <span class="title">{{ t('报告内容') }}</span>
            </div>

            <div class="ai-report-section-body">
              <p>
                {{ t('这里展示 AI 分析生成的报告内容，后续可对接后端接口替换为真实数据。') }}
              </p>
            </div>
          </div>
        </template>

        <template v-else>
          <report-editor
            :content="editContent"
            :title="editTitle"
            @update:content="val => editContent = val"
            @update:title="val => editTitle = val" />
        </template>
      </div>
      <template
        v-if="isEditing"
        #footer>
        <div class="ai-report-edit-footer">
          <bk-button
            class="mr8"
            theme="primary"
            @click="handleSave">
            {{ t('保存') }}
          </bk-button>
          <bk-button @click="handleCancelEdit">
            {{ t('取消') }}
          </bk-button>
        </div>
      </template>
    </audit-sideslider>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ReportEditor from './report-editor.vue';

  interface MetaItem {
    key: string,
    label: string,
    value: string,
  }

  interface Props {
    isShow: boolean;
    title: string;
    metaList?: MetaItem[];
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    title: '',
    metaList: () => [],
  });

  const emit = defineEmits(['update:isShow']);

  const show = computed({
    get: () => props.isShow,
    set: (val: boolean) => emit('update:isShow', val),
  });

  const { t } = useI18n();
  const metaList = computed(() => props.metaList || []);

  const isFullscreen = ref(false);
  const drawerWidth = computed(() => (isFullscreen.value ? '100vw' : 960));

  const isEditing = ref(false);
  const editTitle = ref('');
  const editContent = ref('');
  const headerTitle = computed(() => (isEditing.value ? t('编辑报告') : props.title));

  const handleEdit = () => {
    isEditing.value = true;
    editTitle.value = props.title;
    editContent.value = '';
  };

  const handleExport = (type: 'pdf' | 'markdown') => {
    // TODO: 导出功能占位，根据 type 调用实际导出逻辑
    console.log('handleExport', type);
  };

  const handleToggleFullscreen = () => {
    isFullscreen.value = !isFullscreen.value;
  };

  const handleSave = () => {
    // 这里仅切回预览态，占位后续保存逻辑
    isEditing.value = false;
  };

  const handleCancelEdit = () => {
    isEditing.value = false;
  };
</script>

<style scoped lang="postcss">
.ai-report-header {
  position: relative;
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  border-bottom: 1px solid #dcdee5;
}

.ai-report-title-text {
  font-size: 16px;
  font-weight: 600;
}

.ai-report-header-actions {
  position: absolute;
  right: 20px;
  display: flex;
  align-items: center;
}

.ai-report-fullscreen-icon {
  font-size: 20px;
  color: #979ba5;
  cursor: pointer;

  &:hover {
    color: #3a84ff;
  }
}

.ai-report-preview-body {
  font-size: 13px;
  line-height: 1.6;
  color: #63656e;
}

.ai-report-meta {
  padding: 16px 24px;
  background: #f5f7fa;
  border: 1px solid #e1e6f0;
  border-bottom: none;
  border-radius: 2px 2px 0 0;
}

.ai-report-meta-row {
  display: flex;
  justify-content: space-between;
}

.ai-report-meta-item {
  min-width: 0;
}

.ai-report-meta-item .label {
  margin-bottom: 4px;
  font-size: 12px;
  color: #979ba5;
}

.ai-report-meta-item .value {
  font-size: 13px;
  color: #313238;
}

.ai-report-section {
  padding: 0 0 16px;
  margin-top: 0;
  background: #fff;
  border: 1px solid #e1e6f0;
  border-radius: 0 0 2px 2px;
}

.ai-report-section-header {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid #e1e6f0;
}

.ai-report-section-icon {
  width: 20px;
  height: 20px;
  margin-right: 5px;
}

.ai-report-section-header .title {
  font-size: 16px;
  font-weight: 700;
  color: #313238;
}

.ai-report-section-body {
  padding: 16px 24px 24px;
  background: #fff;
}

.ai-report-edit-form {
  padding: 24px 32px 32px;
  background: #fff;
}

.ai-report-edit-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  height: 52px;
  padding: 0 24px;
}

</style>

