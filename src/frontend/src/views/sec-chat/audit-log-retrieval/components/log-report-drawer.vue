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
  <audit-sideslider
    :before-close="handleBeforeClose"
    :is-show="isShow"
    :quick-close="false"
    :show-footer="isEditing"
    show-footer-slot
    show-header-slot
    title=""
    :width="drawerWidth"
    @update:is-show="handleUpdateShow">
    <template #header>
      <div class="ai-report-header">
        <div class="ai-report-title-wrapper">
          <span class="ai-report-title-text">{{ isEditing ? '编辑报告' : displayTitle }}</span>
        </div>
        <div
          v-if="!isEditing"
          class="ai-report-header-actions">
          <bk-button
            class="mr8"
            @click="handleEdit">
            编辑
          </bk-button>
          <bk-dropdown
            placement="bottom-end"
            trigger="click">
            <bk-button>
              <audit-icon
                class="mr4"
                type="download" />
              导出
            </bk-button>
            <template #content>
              <bk-dropdown-menu>
                <bk-dropdown-item @click="handleExport('pdf')">
                  导出为 PDF
                </bk-dropdown-item>
                <bk-dropdown-item @click="handleExport('markdown')">
                  导出为 Markdown
                </bk-dropdown-item>
              </bk-dropdown-menu>
            </template>
          </bk-dropdown>
        </div>
      </div>
    </template>

    <div class="ai-report-preview-body">
      <template v-if="!isEditing">
        <div class="ai-report-meta">
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
            <div class="ai-report-section-title">
              <img
                alt=""
                class="ai-report-section-icon"
                :src="aiIcon">
              <span class="title">报告内容</span>
            </div>
          </div>
          <div class="ai-report-section-body">
            <div
              v-for="(section, index) in reportSections"
              :key="section.title"
              class="report-block">
              <h4>{{ numberMap[index] }}、{{ section.title }}</h4>
              <p>{{ section.content }}</p>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="edit-form">
          <div class="edit-field">
            <div class="edit-label">
              报告名称
            </div>
            <bk-input v-model="editTitle" />
          </div>
          <div class="edit-field">
            <div class="edit-label">
              报告内容
            </div>
            <bk-input
              v-model="editContent"
              :rows="18"
              type="textarea" />
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <div class="ai-report-edit-footer">
        <bk-button
          style="width: 102px;"
          theme="primary"
          @click="handleSave">
          保存
        </bk-button>
        <bk-button
          style="min-width: 64px;"
          @click="handleCancelEdit">
          取消
        </bk-button>
      </div>
    </template>
  </audit-sideslider>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';

  import useMessage from '@hooks/use-message';

  import aiIcon from '@images/ai-icon.svg';

  import type { RetrievalFilterCondition } from '../../types';

  export interface LogReportInfo {
    id: string;
    type: 'analyze' | 'statistics';
    title: string;
    createdAt: string;
  }

  const props = withDefaults(defineProps<{
    isShow?: boolean;
    report?: LogReportInfo | null;
    totalHit?: number;
    conditions?: RetrievalFilterCondition[];
    systems?: string;
  }>(), {
    isShow: false,
    report: null,
    totalHit: 0,
    conditions: () => [],
    systems: '已选系统',
  });

  const emit = defineEmits<{
    'update:isShow': [value: boolean];
  }>();

  const { messageSuccess } = useMessage();

  const isEditing = ref(false);
  const editTitle = ref('');
  const editContent = ref('');
  const savedTitle = ref('');
  const savedContent = ref('');

  const numberMap = ['一', '二', '三', '四', '五', '六'];

  const isShow = computed({
    get: () => props.isShow,
    set: val => emit('update:isShow', val),
  });

  const drawerWidth = 1100;

  const displayTitle = computed(() => savedTitle.value || props.report?.title || '智能分析报告');

  const conditionText = computed(() => {
    if (!props.conditions.length) return '--';
    return props.conditions.map(item => `${item.field}=${item.value}`).join('，');
  });

  const metaList = computed(() => [
    { key: 'systems', label: '系统范围', value: props.systems || '--' },
    { key: 'conditions', label: '查询条件', value: conditionText.value },
    { key: 'total', label: '总命中数', value: `${props.totalHit.toLocaleString('en-US')}条` },
    { key: 'scope', label: '分析口径', value: '全量数据' },
  ]);

  const defaultSections = computed(() => {
    if (props.report?.type === 'statistics') {
      return [
        { title: '总量趋势', content: '近周期内命中日志量整体呈波动趋势，高峰集中在工作日白天时段。' },
        { title: '操作结果分布', content: '成功操作占比约 78%，失败操作主要集中在权限校验与接口超时场景。' },
        { title: '来源系统分布', content: '日志主要来自蓝盾、云安全审计及业务系统，需关注跨系统关联行为。' },
        { title: '操作人活跃度', content: '头部操作人贡献了大部分变更类操作，建议结合权限策略进一步核查。' },
      ];
    }
    return [
      { title: '行为链分析', content: '基于检索结果还原关键操作链路，识别异常跳转与高频敏感动作。' },
      { title: '风险关联分析', content: '将删除/下载等高风险操作与账号、IP、系统进行关联，定位潜在风险点。' },
      { title: '意图判断', content: '结合操作时间窗与操作组合，判断更可能属于正常运维还是异常探查。' },
      { title: '关联人员挖掘', content: '挖掘同 IP、同系统、同时间窗的关联操作人，辅助扩大调查范围。' },
      { title: '建议下一步调查', content: '建议继续核验权限变更记录，并复核相关资产的访问与导出行为。' },
      { title: '风险影响评估', content: '当前命中规模较大，建议优先处置高危动作并沉淀持续监测规则。' },
    ];
  });

  const reportSections = computed(() => defaultSections.value);

  const buildDefaultContent = () => reportSections.value
    .map((item, index) => `${numberMap[index]}、${item.title}\n${item.content}`)
    .join('\n\n');

  const syncFromReport = () => {
    savedTitle.value = props.report?.title || '智能分析报告';
    savedContent.value = buildDefaultContent();
    editTitle.value = savedTitle.value;
    editContent.value = savedContent.value;
    isEditing.value = false;
  };

  watch(() => [props.isShow, props.report?.id], () => {
    if (props.isShow) syncFromReport();
  });

  const handleUpdateShow = (val: boolean) => {
    emit('update:isShow', val);
  };

  const handleEdit = () => {
    editTitle.value = savedTitle.value;
    editContent.value = savedContent.value;
    isEditing.value = true;
  };

  const handleCancelEdit = () => {
    isEditing.value = false;
    editTitle.value = savedTitle.value;
    editContent.value = savedContent.value;
  };

  const handleSave = () => {
    savedTitle.value = editTitle.value.trim() || savedTitle.value;
    savedContent.value = editContent.value;
    isEditing.value = false;
    messageSuccess('保存成功');
  };

  const handleBeforeClose = () => {
    if (isEditing.value) {
      handleCancelEdit();
      return false;
    }
    return true;
  };

  const handleExport = (mode: 'pdf' | 'markdown') => {
    messageSuccess(mode === 'pdf' ? '已选择导出为 PDF' : '已选择导出为 Markdown');
  };
</script>

<style lang="postcss" scoped>
  .ai-report-header {
    position: relative;
    display: flex;
    width: 100%;
    height: 52px;
    border-bottom: 1px solid #dcdee5;
    align-items: center;
    justify-content: space-between;
  }

  .ai-report-title-text {
    font-size: 16px;
    font-weight: 600;
    color: #313238;
  }

  .ai-report-header-actions {
    position: absolute;
    right: 20px;
    display: flex;
    align-items: center;
  }

  .mr4 {
    margin-right: 4px;
  }

  .mr8 {
    margin-right: 8px;
  }

  .ai-report-preview-body {
    font-size: 13px;
    line-height: 1.6;
    color: #63656e;
  }

  .ai-report-meta {
    padding: 16px 40px;
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
  }

  .ai-report-meta-item {
    min-width: 0;
    flex: 1;

    .label {
      margin-bottom: 6px;
      font-size: 12px;
      color: #979ba5;
    }

    .value {
      font-size: 13px;
      line-height: 20px;
      color: #313238;
      word-break: break-all;
    }
  }

  .ai-report-section {
    min-height: 360px;
    border: 1px solid #e1e6f0;
    border-radius: 0 0 2px 2px;
  }

  .ai-report-section-header {
    display: flex;
    height: 48px;
    padding: 0 24px;
    border-bottom: 1px solid #e1e6f0;
    align-items: center;
  }

  .ai-report-section-title {
    display: flex;
    align-items: center;
    gap: 8px;

    .ai-report-section-icon {
      width: 18px;
      height: 18px;
    }

    .title {
      font-size: 14px;
      font-weight: 700;
      color: #313238;
    }
  }

  .ai-report-section-body {
    padding: 24px 40px 32px;
  }

  .report-block {
    margin-bottom: 20px;

    h4 {
      margin: 0 0 8px;
      font-size: 14px;
      font-weight: 700;
      color: #313238;
    }

    p {
      margin: 0;
      font-size: 13px;
      line-height: 22px;
      color: #63656e;
    }
  }

  .edit-form {
    padding: 24px;
  }

  .edit-field {
    margin-bottom: 16px;

    .edit-label {
      margin-bottom: 8px;
      font-size: 12px;
      color: #63656e;
    }
  }

  .ai-report-edit-footer {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
</style>
