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
          <span class="bksec-detail-label">
            <span
              v-bk-tooltips="labelTip('risk-type', t('风险类型'))"
              class="bksec-detail-label-text"
              @mouseenter="syncLabelOverflow($event, 'risk-type')">{{ t('风险类型') }}：</span>
          </span>
          <span class="bksec-detail-value is-type">{{ riskTypeLabel }}</span>
        </div>
        <div
          v-for="field in fields"
          :key="field.id"
          class="bksec-detail-row">
          <span class="bksec-detail-label">
            <span
              v-bk-tooltips="labelTip(field.id, fieldName(field))"
              class="bksec-detail-label-text"
              @mouseenter="syncLabelOverflow($event, field.id)">{{ fieldName(field) }}：</span>
          </span>
          <span class="bksec-detail-value">{{ displayValue(field.id) }}</span>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BksecManageService from '@service/bksec-manage';

  import type BksecRiskType from '@model/bksec/risk-type';
  import BksecRiskTypeField from '@model/bksec/risk-type-field';
  import type StrategyModel from '@model/strategy/strategy';

  interface Props {
    data: StrategyModel;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const fields = ref<BksecRiskTypeField[]>([]);

  const enabled = computed(() => !!props.data?.bksecEnabled);
  const riskTypeId = computed(() => props.data?.bksecRiskTypeId ?? null);
  const fieldValues = computed(() => props.data?.bksecFieldValues || {});
  const riskTypeLabel = computed(() => {
    const name = props.data?.bksecRiskTypeName || '';
    if (!riskTypeId.value && !name) return '--';
    return name && riskTypeId.value ? `${name}(${riskTypeId.value})` : (name || String(riskTypeId.value));
  });

  const fieldName = (field: BksecRiskTypeField) => field.name || field.id;

  const displayValue = (fieldId: string) => {
    const value = fieldValues.value[fieldId];
    return value === undefined || value === null || value === '' ? '--' : value;
  };

  const labelOverflowed = reactive<Record<string, boolean>>({});
  const syncLabelOverflow = (event: MouseEvent, key: string) => {
    const el = event.currentTarget as HTMLElement;
    labelOverflowed[key] = el.scrollWidth > el.clientWidth;
  };
  const labelTip = (key: string, content: string) => ({
    content,
    disabled: !labelOverflowed[key],
    delay: 80,
  });

  watch(riskTypeId, async (id) => {
    const stored = props.data?.bksecFieldMeta || [];
    if (!id) {
      fields.value = stored.map(item => new BksecRiskTypeField({
        key: item.key,
        name: item.name,
        required: item.required,
      }));
      return;
    }
    try {
      const types = await BksecManageService.fetchRiskTypes();
      const matched = types.find((item: BksecRiskType) => item.id === String(id));
      fields.value = matched?.fields?.length
        ? matched.fields
        : stored.map(item => new BksecRiskTypeField({
          key: item.key,
          name: item.name,
          required: item.required,
        }));
    } catch {
      fields.value = stored.map(item => new BksecRiskTypeField({
        key: item.key,
        name: item.name,
        required: item.required,
      }));
    }
  }, { immediate: true });
</script>
<style lang="postcss" scoped>
.bksec-detail-empty {
  margin-top: var(--audit-space-24);
}

.bksec-detail-list {
  display: grid;
  grid-template-columns: minmax(0, 124px) minmax(0, 1fr);
  width: 1000px;
  column-gap: var(--audit-space-8);
  font-size: var(--audit-font-size-sm);
  line-height: var(--audit-line-height-sm);
}

.bksec-detail-row {
  display: contents;
}

.bksec-detail-label,
.bksec-detail-value {
  min-height: 32px;
  padding: 6px 0;
}

.bksec-detail-label {
  max-width: 124px;
  min-width: 0;
  overflow: hidden;
}

.bksec-detail-label-text {
  display: block;
  max-width: 100%;
  overflow: hidden;
  color: var(--audit-neutral-text-02);
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bksec-detail-value {
  min-width: 0;
  color: var(--audit-neutral-text-01);
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

.bksec-detail-value.is-type {
  color: var(--audit-neutral-text-02);
}
</style>
