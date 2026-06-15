<template>
  <div>
    <audit-sideslider
      v-model:isShow="show"
      :before-close="handleBeforeClose"
      :quick-close="false"
      :show-footer="isEditing"
      show-footer-slot
      show-header-slot
      title=""
      :width="drawerWidth">
      <template #header>
        <div class="ai-report-header">
          <div class="ai-report-title-wrapper">
            <span class="ai-report-title-text">{{ title }}</span>
          </div>
          <div
            class="ai-report-header-actions">
            <bk-button
              v-if="!isEditing"
              class="mr8"
              @click="handleEdit">
              {{ t('编辑') }}
            </bk-button>
            <bk-dropdown
              v-if="!isEditing"
              trigger="click">
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
                class="ai-report-meta-item"
                :class="`ai-report-meta-item--${item.key}`">
                <div class="label">
                  {{ item.label }}
                </div>
                <div class="value">
                  <div v-if="item.key === 'analysis_scope'">
                    <div
                      v-for="(scope, index) in item.value"
                      :key="index"
                      class="ai-report-meta-scope-item">
                      <span
                        v-if="scope.label === '首次发现时间'"
                        class="ai-report-meta-text-full">
                        {{ scope.label }} = {{ scope.value }}
                      </span>
                      <tooltips
                        v-else
                        :data="`${scope.label} = ${scope.value}`"
                        :max-width="tooltipMaxWidth" />
                    </div>
                  </div>
                  <span
                    v-else-if="item.key === 'created_at'"
                    class="ai-report-meta-text-full">
                    {{ item.value }}
                  </span>
                  <tooltips
                    v-else
                    :data="String(item.value ?? '')"
                    :max-width="tooltipMaxWidth" />
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
              <!-- eslint-disable vue/no-v-html -->
              <div
                class="markdowm-container"
                v-html="htmlText" />
            </div>
          </div>
        </template>

        <template v-else>
          <report-editor
            :content="editContent"
            :title="editTitle"
            @update:content="(val:string) => editContent = val"
            @update:title="(val:string) => editTitle = val" />
        </template>
      </div>
      <template #footer>
        <div class="ai-report-edit-footer">
          <bk-button
            :loading="saveLoading"
            style="width: 102px;"
            theme="primary"
            @click="handleSave">
            {{ t('保存') }}
          </bk-button>
          <bk-button
            style="min-width: 64px;"
            @click="handleCancelEdit">
            {{ t('取消') }}
          </bk-button>
        </div>
      </template>
    </audit-sideslider>
  </div>
</template>

<script setup lang="ts">
  import { Message } from 'bkui-vue';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useRequest from '@hooks/use-request';

  import ReportEditor from './report-editor.vue';
  import { toPreviewHtml } from './report-content-utils';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import RiskManageService from '@/domain/service/risk-manage';

  interface Props {
    isShow: boolean;
    itemInfo: string;
  }
  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    itemInfo: '',
  });

  const emit = defineEmits(['update:isShow', 'refresh', 'update:item-info']);

  const { t } = useI18n();
  const isFullscreen = ref(false);
  const isEditing = ref(false);
  const editContent = ref('');
  const editTitle = ref('');

  const syncEditFormFromItemInfo = () => {
    if (!props.itemInfo) {
      editContent.value = '';
      editTitle.value = '';
      return;
    }
    try {
      const info = JSON.parse(props.itemInfo);
      editContent.value = info.content || '';
      editTitle.value = info.title || '';
    } catch {
      editContent.value = '';
      editTitle.value = '';
    }
  };

  const exitEditMode = () => {
    isEditing.value = false;
    syncEditFormFromItemInfo();
  };

  const metaList = computed(() => {
    if (!props.itemInfo) {
      return [];
    }
    try {
      const info = JSON.parse(props.itemInfo);
      return [
        {
          key: 'report_type',
          label: t('报告类型'),
          value: info.report_type === 'system' ? t('系统分析') : t('自定义分析'),
        },
        {
          key: 'analysis_scope',
          label: t('分析范围'),
          value: JSON.parse(info.analysis_scope)?.map((item: any) => {
            if (item.label === '首次发现时间') {
              return  {
                label: item.label,
                value: Array.isArray(item.value) ? item.value.join('-') : item.value,
              };
            }
            return {
              label: item.label,
              value: Array.isArray(item.value) ? item.value.join(',') : item.value,
            };
          }),
        },
        {
          key: 'risk_count',
          label: t('风险条数'),
          value: info.risk_count,
        },
        {
          key: 'created_by',
          label: t('生成人'),
          value: info.created_by,
        },
        {
          key: 'created_at',
          label: t('生成时间'),
          value: info.created_at,
        },
      ];
    } catch {
      return [];
    }
  });
  const title = computed(() => JSON.parse(props.itemInfo).title || '');
  const drawerWidth = computed(() => (isFullscreen.value ? '100vw' : 960));
  const tooltipMaxWidth = computed(() => (
    isFullscreen.value ? 'calc(100vw - 48px)' : 912
  ));
  const show = computed({
    get: () => props.isShow,
    set: (val: boolean) => emit('update:isShow', val),
  });
  const htmlText = computed(() => {
    if (!props.itemInfo) return '';
    try {
      const rawContent = JSON.parse(props.itemInfo).content || '';
      return toPreviewHtml(rawContent);
    } catch {
      return '';
    }
  });
  const handleEdit = () => {
    syncEditFormFromItemInfo();
    isEditing.value = true;
  };

  // 导出AI报告
  const {
    run: exportAiAnalyseReport,
  } = useRequest(RiskManageService.exportAiAnalyseReport, {
    defaultValue: null,
    onSuccess(data) {
      if (data?.download_url) {
        window.open(data.download_url);
      }
      Message({ theme: 'success', message: t('导出成功') });
    },
  });

  const handleExport = (type: 'pdf' | 'markdown') => {
    const reportInfo = JSON.parse(props.itemInfo);
    exportAiAnalyseReport({
      report_id: reportInfo.report_id,
      export_format: type,
    });
  };

  const handleToggleFullscreen = () => {
    isFullscreen.value = !isFullscreen.value;
  };
  // 保存AI报告
  const {
    loading: saveLoading,
    run: updateAiAnalyseReport,
  } = useRequest(RiskManageService.updateAiAnalyseReport, {
    defaultValue: [],
    onSuccess(data) {
      // 通知父组件更新itemInfo为最新的数据
      emit('update:item-info', JSON.stringify(data));

      // 保存成功后提示并切换回预览状态
      Message({ theme: 'success', message: t('保存成功') });
      exitEditMode();
      // 通知父组件刷新列表
      emit('refresh');
    },
  });
  const handleSave = () => {
    const reportInfo = JSON.parse(props.itemInfo);
    updateAiAnalyseReport({
      report_id: reportInfo.report_id,
      title: editTitle.value,
      content: editContent.value,
    });
  };

  const handleCancelEdit = () => {
    exitEditMode();
  };

  // 编辑状态下阻止侧边栏收起
  const handleBeforeClose = () => {
    if (isEditing.value) {
      exitEditMode();
      return false;
    }
    return true;
  };

  watch(show, (val) => {
    if (!val) {
      isFullscreen.value = false;
      exitEditMode();
    }
  });
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

.ai-report-title-wrapper {
  min-width: 0;
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
  gap: 24px;
  align-items: flex-start;
  justify-content: space-between;
  text-align: center;
}

.ai-report-meta-item {
  min-width: 0;
  overflow: hidden;
}

.ai-report-meta-item--report_type {
  flex: 0 0 72px;
}

.ai-report-meta-item--analysis_scope {
  flex: 1 1 0;
  min-width: 280px;
}

.ai-report-meta-item--risk_count {
  flex: 0 0 64px;
}

.ai-report-meta-item--created_by {
  flex: 0 0 100px;
}

.ai-report-meta-item--created_at {
  flex: 0 0 155px;
  overflow: visible;
}

.ai-report-meta-text-full {
  display: inline-block;
  white-space: nowrap;
}

.ai-report-meta-item .label {
  margin-bottom: 4px;
  font-size: 12px;
  color: #979ba5;
}

.ai-report-meta-item .value {
  width: 100%;
  font-size: 13px;
  color: #313238;
}

.ai-report-meta-scope-item {
  width: 100%;
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

.ai-report-edit-footer {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
}

:deep(.bk-sideslider-footer),
:deep(.bk-modal-footer) {
  display: flex;
  width: 100%;
  padding-right: 24px;
  padding-left: 24px;
  box-sizing: border-box;
  justify-content: flex-start;
}

:deep(.bk-sideslider-header),
:deep(.bk-modal-header) {
  padding-right: 24px;
  padding-left: 24px;
  box-sizing: border-box;
}

/* Markdown 表格样式 - 使用 :deep() 穿透 scoped 样式 */
.markdowm-container {
  :deep(table) {
    width: 100%;
    margin: 16px 0;
    font-size: 13px;
    border-collapse: collapse;
  }

  :deep(th),
  :deep(td) {
    padding: 10px 12px;
    text-align: left;
    border: 1px solid #dcdee5;
  }

  :deep(th) {
    font-weight: 600;
    color: #313238;
    background-color: #f5f7fa;
  }

  :deep(td) {
    color: #63656e;
  }

  :deep(tr:hover td) {
    background-color: #f5f7fa;
  }

  :deep(thead tr) {
    background-color: #f5f7fa;
  }

  :deep(tbody tr:nth-child(even)) {
    background-color: #fafbfd;
  }
}

</style>
