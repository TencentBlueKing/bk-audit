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
      multiple
      multiple-mode="tag"
      :model-value="selectedKinds"
      selected-style="checkbox"
      :placeholder="t('请选择需要添加的限制')"
      @change="handleKindsChange">
      <bk-option
        id="type"
        :name="t('账号类型')" />
      <bk-option
        v-if="hasAccountTypeRow"
        id="__none__"
        disabled
        :name="t('已添加全部限制项')" />
    </bk-select>
    <div
      v-if="accountRow"
      class="usage-restriction-table">
      <div class="usage-restriction-head">
        <span>{{ t('限制项') }}</span>
        <span>{{ t('限制配置') }}</span>
        <span />
      </div>
      <div class="usage-restriction-row">
        <span class="usage-restriction-cell">{{ t('账号类型') }}</span>
        <div
          class="usage-restriction-cell usage-restriction-config"
          :class="{ 'is-open': panelOpen }"
          data-testid="portrait-usage-restriction-config"
          @click="togglePanel">
          <span class="usage-restriction-prefix">{{ t('仅允许') }}：</span>
          <span
            v-if="!accountRow.allowed.length"
            class="usage-restriction-placeholder">
            {{ t('请选择取值') }}
          </span>
          <span
            v-for="item in selectedTags"
            :key="item.value"
            class="usage-restriction-tag">
            {{ item.label }}
            <button
              class="usage-restriction-tag-close"
              type="button"
              @click.stop="removeAllowed(item.value)">
              ×
            </button>
          </span>
        </div>
        <div class="usage-restriction-cell usage-restriction-op">
          <bk-button
            text
            theme="primary"
            @click="handleRemove">
            {{ t('删除') }}
          </bk-button>
        </div>
      </div>
    </div>
    <teleport to="body">
      <div
        v-if="panelOpen"
        class="usage-restriction-panel"
        :style="panelStyle"
        @click.stop>
        <label
          v-for="item in accountTypeOptions"
          :key="item.value"
          class="usage-restriction-option">
          <input
            :checked="accountRow?.allowed.includes(item.value)"
            type="checkbox"
            @change="toggleAllowed(item.value)">
          <span>{{ item.label }}</span>
        </label>
        <div class="usage-restriction-foot">
          {{ t('已选 {count} 项 · 未勾选的取值将对该可见范围不可用', { count: accountRow?.allowed.length || 0 }) }}
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import {
    PORTRAIT_ACCOUNT_TYPES,
    portraitAccountLabel,
    type UsageRestrictionRow,
  } from '@utils/tool/portrait-account-restriction';

  interface Props {
    rows?: UsageRestrictionRow[];
  }

  interface Emits {
    (e: 'update:rows', value: UsageRestrictionRow[]): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    rows: () => [],
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const panelOpen = ref(false);
  const panelStyle = ref<Record<string, string>>({});
  const configRef = ref<HTMLElement | null>(null);
  const accountRow = computed(() => props.rows.find(item => item.param === 'type'));
  const hasAccountTypeRow = computed(() => !!accountRow.value);
  const selectedKinds = computed(() => (hasAccountTypeRow.value ? ['type'] : []));
  const accountTypeOptions = PORTRAIT_ACCOUNT_TYPES.map(item => ({
    value: item.value,
    label: item.value === 'openid' ? item.label : t(portraitAccountLabel(item.value)),
  }));
  const selectedTags = computed(() => accountTypeOptions.filter(item => accountRow.value?.allowed.includes(item.value)));

  const setAllowed = (allowed: string[]) => {
    emit('update:rows', props.rows.map(item => (
      item.param === 'type' ? { ...item, allowed } : item
    )));
  };

  const handleKindsChange = (value: string | string[]) => {
    const list = Array.isArray(value) ? value : [value];
    if (!list.includes('type') || hasAccountTypeRow.value) return;
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

  const placePanel = () => {
    const anchor = configRef.value;
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    panelStyle.value = {
      top: `${rect.bottom}px`,
      left: `${rect.left}px`,
      width: `${rect.width}px`,
    };
  };

  const togglePanel = (event: MouseEvent) => {
    configRef.value = event.currentTarget as HTMLElement;
    panelOpen.value = !panelOpen.value;
    if (panelOpen.value) {
      nextTick(placePanel);
    }
  };

  const closePanel = () => {
    panelOpen.value = false;
  };

  const onOutside = (event: Event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest('.usage-restriction-config, .usage-restriction-panel')) return;
    closePanel();
  };

  const toggleAllowed = (value: string) => {
    const allowed = accountRow.value?.allowed || [];
    setAllowed(allowed.includes(value) ? allowed.filter(item => item !== value) : [...allowed, value]);
  };

  const removeAllowed = (value: string) => {
    setAllowed((accountRow.value?.allowed || []).filter(item => item !== value));
  };

  const handleRemove = () => {
    closePanel();
    emit('update:rows', props.rows.filter(item => item.param !== 'type'));
  };

  onMounted(() => {
    document.addEventListener('click', onOutside);
    window.addEventListener('resize', closePanel);
    window.addEventListener('scroll', closePanel, true);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', onOutside);
    window.removeEventListener('resize', closePanel);
    window.removeEventListener('scroll', closePanel, true);
  });
</script>

<style lang="postcss" scoped>
  .usage-restriction-title {
    display: flex;
    align-items: center;
    margin-bottom: 4px;
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

  .usage-restriction {
    margin-bottom: 8px;
  }

  .usage-restriction-add,
  .usage-restriction-table {
    width: 100%;
    max-width: 720px;
  }

  .usage-restriction-table {
    margin-top: 8px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .usage-restriction-head,
  .usage-restriction-row {
    display: grid;
    grid-template-columns: 160px minmax(0, 1fr) 64px;
  }

  .usage-restriction-head {
    background: #fafbfd;
  }

  .usage-restriction-head span,
  .usage-restriction-cell {
    display: flex;
    align-items: center;
    box-sizing: border-box;
    min-height: 36px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    border-right: 1px solid #eaebf0;
  }

  .usage-restriction-head span:last-child,
  .usage-restriction-op {
    border-right: none;
  }

  .usage-restriction-row {
    border-top: 1px solid #eaebf0;
  }

  .usage-restriction-config {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
    min-height: 36px;
    cursor: pointer;
  }

  .usage-restriction-config.is-open {
    background: #f0f5ff;
  }

  .usage-restriction-prefix,
  .usage-restriction-placeholder {
    color: #c4c6cc;
  }

  .usage-restriction-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 22px;
    padding: 0 6px;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;
  }

  .usage-restriction-tag-close {
    padding: 0;
    font-size: 14px;
    line-height: 1;
    color: #979ba5;
    cursor: pointer;
    background: none;
    border: none;
  }

  .usage-restriction-op {
    display: flex;
    align-items: center;
    justify-content: center;
  }
</style>

<style lang="postcss">
  .usage-restriction-panel {
    position: fixed;
    z-index: 3000;
    background: #fff;
    border: 1px solid #dcdee5;
    box-shadow: 0 0 10px 0 rgb(0 0 0 / 10%);
  }

  .usage-restriction-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
  }

  .usage-restriction-foot {
    padding: 8px 12px;
    font-size: 12px;
    color: #979ba5;
    border-top: 1px solid #eaebf0;
  }
</style>
