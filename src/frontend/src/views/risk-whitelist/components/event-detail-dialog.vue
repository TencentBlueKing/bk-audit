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
            <td class="type-cell">{{ item.field_type }}</td>
            <td class="value-cell">
              <show-tooltips-text
                :data="formatFieldValue(item.field_value)"
                :line="4"
                :max-width="360"
                placement="top"
                tooltip-content-class="show-tooltips-text-popup"
                tooltip-max-height="40vh" />
            </td>
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

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  const { t } = useI18n();
  const isShow = ref(false);
  const loading = ref(false);
  const fields = ref<EventFieldRow[]>([]);

  const formatFieldValue = (value: unknown) => {
    if (value === undefined || value === null || value === '') return '--';
    if (typeof value === 'string') return value;
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  };

  const open = (whitelistId: number | string, hitId: number | string) => {
    isShow.value = true;
    loading.value = true;
    fields.value = [];
    RiskWhitelistService.fetchHitEvents({ id: whitelistId, hit_id: hitId }).then((data) => {
      fields.value = data;
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
    table-layout: fixed;
    border-collapse: collapse;
  }

  .event-table tr {
    height: 42px;
  }

  .event-table th,
  .event-table td {
    height: 42px;
    padding: var(--bk-theme-space-8) var(--bk-theme-space-16);
    font-family: var(--bk-theme-font-family);
    font-size: var(--bk-theme-font-size-sm);
    font-weight: var(--bk-theme-font-weight-regular);
    line-height: var(--bk-theme-line-height-base);
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid var(--bk-theme-border-weak);
    box-sizing: border-box;
  }

  .event-table th {
    color: var(--bk-theme-text-strong);
    white-space: nowrap;
    background: var(--bk-theme-surface-subtle);
  }

  .event-table th:nth-child(1),
  .event-table td:nth-child(1) {
    width: 112px;
  }

  .event-table th:nth-child(2),
  .event-table td:nth-child(2) {
    width: 112px;
  }

  .event-table th:nth-child(3),
  .event-table td:nth-child(3) {
    width: 64px;
  }

  .event-table td {
    color: var(--bk-theme-text-default);
    word-break: break-all;
  }

  .type-cell {
    white-space: nowrap;
  }

  .value-cell {
    min-width: 0;
  }

  :deep(.bk-dialog-footer) {
    display: none;
  }
</style>
