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
  <div class="other-table-detail">
    <bk-button
      class="structure-preview"
      text
      theme="primary"
      @click="dataStructurePreview">
      <audit-icon
        class="structure-preview-icon"
        type="view" />
      {{ t('数据结构预览') }}
    </bk-button>
    <div class="detail-form">
      <div class="detail-row">
        <span class="detail-label">{{ t('数据名称') }}：</span>
        <span class="detail-value">{{ rtMeta.result_table_name || '-' }}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">{{ t('数据ID') }}：</span>
        <span class="detail-value">{{ rtMeta.result_table_id || '-' }}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">{{ t('中文名称') }}：</span>
        <span class="detail-value">{{ rtMeta.result_table_name_alias || '-' }}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">{{ t('数据管理员') }}：</span>
        <span class="detail-value">{{ rtMeta.managers?.join(',') || '-' }}</span>
      </div>
      <div class="detail-row detail-row-tags">
        <span class="detail-label">{{ t('业务运维人员') }}：</span>
        <span class="detail-value">
          <edit-tag
            v-if="bizRoleMembers.length"
            :data="bizRoleMembers"
            :show-copy="false" />
          <template v-else>
            -
          </template>
        </span>
      </div>
      <div class="detail-row">
        <span class="detail-label">{{ t('表类型') }}：</span>
        <span class="detail-value">{{ rtMeta.processing_type || '-' }}</span>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import RtMetaModel from '@model/strategy/rt-meta';

  import EditTag from '@components/edit-box/tag.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    rtId: string | Array<string>;
  }
  interface Emits {
    (e: 'show-structure-preview', rtId: string | Array<string>, currentViewField: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 获取表格信息
  const {
    data: rtMeta,
    run: fetchTableRtMeta,
  } = useRequest(StrategyManageService.fetchTableRtMeta, {
    defaultValue: new RtMetaModel(),
  });
  const bizRoleMembers = computed(() => rtMeta.value.sensitivity_info?.biz_role_memebers || []);

  const dataStructurePreview = () => {
    emit('show-structure-preview', props.rtId, '');
  };

  watch(() => props.rtId, () => {
    fetchTableRtMeta({
      table_id: props.rtId,
    });
  }, {
    immediate: true,
  });
</script>
<style scoped lang="postcss">
  .other-table-detail {
    position: relative;
    width: 624px;
    max-width: 100%;
    padding: 12px 24px;
    margin-top: var(--audit-space-8);
    background-color: var(--audit-neutral-bg-03);
    border-radius: var(--audit-radius-control);
    box-sizing: border-box;
  }

  .structure-preview {
    position: absolute;
    top: 12px;
    right: 16px;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
  }

  .structure-preview-icon {
    margin-right: var(--audit-space-4);
    font-size: 16px;
  }

  .detail-form {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    column-gap: var(--audit-space-8);
    align-items: center;
  }

  .detail-row {
    display: contents;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
  }

  .detail-label {
    min-width: 84px;
    padding: 3px 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    text-align: right;
    white-space: nowrap;
  }

  .detail-value {
    min-width: 0;
    padding: 3px 108px 3px 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-01);
    word-break: break-all;
  }

  .detail-row-tags .detail-label,
  .detail-row-tags .detail-value {
    padding-top: 2px;
    padding-bottom: 2px;
  }

  .other-table-detail :deep(.audit-edit-tag__label.bk-tag) {
    height: 22px;
    padding: 0 var(--audit-space-8);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    background: var(--audit-neutral-border-02);
    border-color: transparent;
    border-radius: var(--audit-radius-control);
  }

  .other-table-detail :deep(.bk-tag ~ .bk-tag) {
    margin-left: var(--audit-space-8);
  }
</style>
