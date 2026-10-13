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
  <div
    class="usage-restriction"
    data-testid="portrait-usage-restriction">
    <div class="usage-restriction-title">
      <span>{{ t('使用限制') }}</span>
      <audit-icon
        v-bk-tooltips="{
          content: t('限制该可见范围内的用户使用本工具的方式；未配置则不做任何限制'),
        }"
        class="usage-restriction-tip"
        type="info-fill" />
    </div>
    <bk-select
      class="usage-restriction-add"
      :clearable="false"
      :model-value="selectedKinds"
      multiple
      multiple-mode="tag"
      :placeholder="t('请选择需要添加的限制')"
      :popover-options="{
        boundary: 'body',
        zIndex: popoverZIndex,
      }"
      @change="handleKindsChange">
      <bk-option
        id="type"
        :name="t('账号类型')" />
    </bk-select>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { UsageRestrictionRow } from '@utils/tool/portrait-account-restriction';

  interface Props {
    rows?: UsageRestrictionRow[];
    popoverZIndex?: number;
  }

  interface Emits {
    (e: 'update:rows', value: UsageRestrictionRow[]): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    rows: () => [],
    popoverZIndex: 2500,
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const hasAccountRow = computed(() => props.rows.some(item => item.param === 'type'));
  const selectedKinds = computed(() => (hasAccountRow.value ? ['type'] : []));

  const handleKindsChange = (value: string | string[]) => {
    const list = Array.isArray(value) ? value : [value];
    if (!list.includes('type')) {
      if (hasAccountRow.value) {
        emit('update:rows', props.rows.filter(item => item.param !== 'type'));
      }
      return;
    }
    if (hasAccountRow.value) return;
    emit('update:rows', [
      ...props.rows,
      {
        id: `ur_${Date.now().toString(36)}`,
        kind: 'allowed_values',
        param: 'type',
        allowed: [],
      },
    ]);
  };
</script>

<style lang="postcss" scoped>
  .usage-restriction {
    margin-bottom: 12px;
  }

  .usage-restriction-title {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
  }

  .usage-restriction-tip {
    margin-left: 4px;
    font-size: 14px;
    color: #979ba5;
    cursor: default;
  }

  .usage-restriction-add {
    width: var(--param-name-col-width, 100%);
  }

  .usage-restriction.is-full-width .usage-restriction-add {
    width: 100%;
  }
</style>
