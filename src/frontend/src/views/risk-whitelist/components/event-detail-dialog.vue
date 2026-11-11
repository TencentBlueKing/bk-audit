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
  <bk-dialog
    v-model:is-show="isShow"
    class="event-detail-dialog"
    :esc-close="false"
    :quick-close="false"
    :title="t('事件详情')"
    width="640">
    <bk-loading :loading="loading">
      <table class="event-table">
        <thead>
          <tr>
            <th>{{ t('字段名') }}</th>
            <th>{{ t('字段中文名') }}</th>
            <th>{{ t('类型') }}</th>
            <th>{{ t('字段值') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in fields"
            :key="item.field">
            <td>{{ item.field }}</td>
            <td>{{ item.field_name }}</td>
            <td>{{ item.field_type }}</td>
            <td>{{ item.field_value }}</td>
          </tr>
          <tr v-if="!fields.length && !loading">
            <td colspan="4">{{ t('暂无数据') }}</td>
          </tr>
        </tbody>
      </table>
    </bk-loading>
    <template #footer />
  </bk-dialog>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskWhitelistService from '@service/risk-whitelist';

  import type { EventFieldRow } from '@model/risk-whitelist/whitelist';

  const { t } = useI18n();
  const isShow = ref(false);
  const loading = ref(false);
  const fields = ref<EventFieldRow[]>([]);

  const open = (id: number | string) => {
    isShow.value = true;
    loading.value = true;
    fields.value = [];
    RiskWhitelistService.fetchHitEvent({ id }).then((data) => {
      fields.value = data.fields || [];
    })
      .finally(() => {
        loading.value = false;
      });
  };

  defineExpose({ open });
</script>
<style lang="postcss" scoped>
  .event-table {
    width: 100%;
    border-collapse: collapse;
  }

  .event-table tr {
    height: 42px;
  }

  .event-table th,
  .event-table td {
    height: 42px;
    padding: 0 var(--bk-theme-space-16);
    font-family: var(--bk-theme-font-family);
    font-size: var(--bk-theme-font-size-sm);
    font-weight: var(--bk-theme-font-weight-regular);
    line-height: var(--bk-theme-line-height-base);
    text-align: left;
    border-bottom: 1px solid var(--bk-theme-border-weak);
    box-sizing: border-box;
  }

  .event-table th {
    color: var(--bk-theme-text-strong);
    background: var(--bk-theme-surface-subtle);
  }

  .event-table td {
    color: var(--bk-theme-text-default);
  }

  :deep(.bk-dialog-footer) {
    display: none;
  }
</style>
