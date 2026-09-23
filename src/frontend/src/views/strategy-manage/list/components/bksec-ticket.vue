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
  <div class="bksec-detail">
    <bk-exception
      v-if="!enabled"
      class="bksec-detail-empty"
      data-testid="bksec-ticket-empty"
      scene="part"
      type="empty">
      {{ t('当前策略未启用BKSEC安全工单') }}
    </bk-exception>
    <template v-else>
      <div class="bksec-detail-list">
        <div class="bksec-detail-row">
          <span class="bksec-detail-label">{{ t('风险类型') }}：</span>
          <span class="is-type">{{ riskTypeLabel }}</span>
        </div>
        <div
          v-for="field in fields"
          :key="field.id"
          class="bksec-detail-row">
          <span class="bksec-detail-label">{{ field.label }}：</span>
          <span>{{ displayValue(field.id) }}</span>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BksecManageService from '@service/bksec-manage';

  import type BksecRiskTypeField from '@model/bksec/risk-type-field';
  import type StrategyModel from '@model/strategy/strategy';

  interface Props {
    data: StrategyModel;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const fields = ref<BksecRiskTypeField[]>([]);
  const typeName = ref('');

  const enabled = computed(() => !!props.data?.bksecEnabled);
  const riskTypeId = computed(() => props.data?.bksecRiskTypeId ?? null);
  const fieldValues = computed(() => props.data?.bksecFieldValues || {});
  const riskTypeLabel = computed(() => (
    riskTypeId.value ? `${typeName.value || ''}(${riskTypeId.value})`.replace(/^\(/, '(') : '--'
  ));

  const displayValue = (fieldId: string) => {
    const value = fieldValues.value[fieldId];
    return value === undefined || value === null || value === '' ? '--' : value;
  };

  watch(riskTypeId, async (id) => {
    if (!id) {
      fields.value = [];
      typeName.value = '';
      return;
    }
    const [types, nextFields] = await Promise.all([
      BksecManageService.fetchRiskTypes(),
      BksecManageService.fetchRiskTypeFields({ risk_type_id: Number(id) }),
    ]);
    typeName.value = types.find(item => item.id === Number(id))?.name || '';
    fields.value = nextFields;
  }, { immediate: true });
</script>
<style lang="postcss" scoped>
.bksec-detail {
  padding: 0 var(--audit-space-40);
}

.bksec-detail-empty {
  margin-top: var(--audit-space-24);
}

.bksec-detail-list {
  width: 320px;
}

.bksec-detail-row {
  display: flex;
  gap: var(--audit-space-8);
  align-items: flex-start;
  min-height: 32px;
  padding: 6px 0;
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
  color: var(--audit-neutral-text-01);
}

.bksec-detail-label {
  flex: 0 0 84px;
  width: 84px;
  overflow: visible;
  color: var(--audit-neutral-text-02);
  text-align: right;
  white-space: nowrap;
}

.is-type {
  color: var(--audit-neutral-text-02);
}
</style>
