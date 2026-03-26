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
                class="ai-report-meta-item">
                <div class="label">
                  {{ item.label }}
                </div>
                <div class="value">
                  <div v-if="item.key === 'analysis_scope'">
                    <div
                      v-for="(scope, index) in item.value"
                      :key="index">
                      {{ scope.label }} = {{ scope.value }}
                    </div>
                  </div>
                  <div v-else>
                    {{ item.value }}
                  </div>
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
  import { Message } from 'bkui-vue';
  import DOMPurify from 'dompurify';
  import MarkdownIt from 'markdown-it';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useRequest from '@hooks/use-request';

  import ReportEditor from './report-editor.vue';

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

  // 初始化markdown渲染器
  const md = new MarkdownIt({
    html: true,
    linkify: true,
    typographer: true,
  });

  const { t } = useI18n();
  const isFullscreen = ref(false);
  const isEditing = ref(false);
  const editContent = ref('');

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
  const editTitle = computed(() => JSON.parse(props.itemInfo).title || '');
  const show = computed({
    get: () => props.isShow,
    set: (val: boolean) => emit('update:isShow', val),
  });
  // 使用markdown-it渲染markdown内容
  const htmlText = computed(() => {
    if (!props.itemInfo) return '';
    try {
      return md.render(DOMPurify.sanitize(JSON.parse(props.itemInfo).content)) || '';
    } catch {
      return '';
    }
  });
  const handleEdit = () => {
    isEditing.value = true;
    try {
      editContent.value = JSON.parse(props.itemInfo).content || '';
    } catch {
      editContent.value = '';
    }
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
    run: updateAiAnalyseReport,
  } = useRequest(RiskManageService.updateAiAnalyseReport, {
    defaultValue: [],
    onSuccess(data) {
      // 通知父组件更新itemInfo为最新的数据
      emit('update:item-info', JSON.stringify(data));

      // 保存成功后提示并切换回预览状态
      Message({ theme: 'success', message: t('保存成功') });
      isEditing.value = false;
      // 通知父组件刷新列表
      emit('refresh');
    },
  });
  const handleSave = async () => {
    const reportInfo = JSON.parse(props.itemInfo);
    updateAiAnalyseReport({
      report_id: reportInfo.report_id,
      title: editTitle.value,
      content: editContent.value,
    });
  };

  const handleCancelEdit = () => {
    isEditing.value = false;
  };

  // 编辑状态下阻止侧边栏收起
  const handleBeforeClose = () => {
    if (isEditing.value) {
      isEditing.value = false;
      return false;
    }
    return true;
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
  align-items: center;
  text-align: center;
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
  width: 96%;
  margin-top: 16px;
  margin-left: 2%;
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
