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
    v-if="renderData.length"
    class="render-field">
    <div class="field-header-row">
      <div class="field-id">
        #
      </div>
      <div class="field-key">
        {{ t('方案输入字段') }}
      </div>
      <div
        class="field-value"
        style="padding-left: 16px;">
        {{ t('参数值') }}
      </div>
    </div>
    <template
      v-for="(fieldItem, fieldIndex) in renderData"
      :key="fieldIndex">
      <div class="field-row">
        <div class="field-id">
          {{ fieldIndex + 1 }}
        </div>
        <div class="field-key">
          <span class="field-type">{{ fieldItem.value_type }}</span>
          <span style="line-height: 20px;">
            {{ fieldItem.variable_name }}（{{ fieldItem.variable_alias }}）
          </span>
        </div>
        <div class="field-value">
          {{ fieldItem.variable_value }}
        </div>
      </div>
    </template>
  </div>
  <div v-else>
    --
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    data: Record<string, any>[];
  }

  const props = defineProps<Props>();

  const { t } = useI18n();


  const renderData = computed(() => props.data || []);
</script>
<style lang="postcss" scoped>
  .render-field {
    display: flex;
    min-width: 640px;
    overflow: hidden;
    border-radius: var(--bk-theme-tag-radius);
    user-select: none;
    flex-direction: column;
    flex: 1;

    .field-id {
      width: 60px;
      text-align: center;
    }

    .field-header-row {
      display: flex;
      height: 42px;
      font-size: 12px;
      line-height: 40px;
      color: var(--bk-theme-text-strong);
      background: var(--bk-theme-table-header-bg);
    }

    .field-row {
      display: flex;
      overflow: hidden;
      font-size: 12px;
      line-height: 42px;
      color: var(--bk-theme-text-default);
      background: var(--bk-theme-surface-default);
      border-top: 1px solid var(--bk-theme-border-default);
    }

    .field-row:last-child {
      border-bottom: 1px solid var(--bk-theme-border-default);
    }

    .field-key {
      position: relative;
      display: flex;
      height: 40px;
      padding-left: var(--bk-theme-space-16);
      align-items: center;
      flex: 1 0 340px;

      .field-type {
        display: inline-block;
        padding: 0 var(--bk-theme-space-12);
        margin-right: var(--bk-theme-space-4);
        line-height: 21px;
        color: var(--bk-theme-color-brand-2);
        background: var(--bk-theme-fill-selected);
        border-radius: var(--bk-theme-message-radius);
      }

      .field-type-icon {
        width: 46px;
        margin-right: var(--bk-theme-space-6);
      }

      .field-required {
        margin-right: var(--bk-theme-space-12);
        margin-left: auto;
        color: var(--bk-theme-color-danger-2);
      }
    }

    .field-value {
      padding-left: var(--bk-theme-space-16);
      overflow: hidden;
      flex: 1 1 320px;
    }
  }
</style>
