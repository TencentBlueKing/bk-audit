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
  <div class="strategy-upgrade-card">
    <p class="title">
      {{ title }}
    </p>
    <div class="table-content">
      <div
        v-for="item in column"
        :key="item.label"
        class="table-tr"
        :class="{
          'disabled': item.disabled,
          'highlight': item.highlight,
        }">
        <div class="tr-title ">
          <img
            v-if="item.type"
            class="field-type-icon"
            :src="getFieldTypeIcon(item.type, { highlight: item.highlight })">
          <tool-tip
            class="content"
            :data="item.label" />
        </div>
        <p class="tr-content">
          {{ item.value || '--' }}
        </p>
      </div>
    </div>
    <div
      v-if="inputFieldsMap && inputFieldsMap.length"
      class="fields-map">
      <p style="margin-bottom: var(--bk-theme-space-8)">
        {{ t('输入字段映射') }}
      </p>
      <template
        v-for="(mapItem,index) in inputFieldsMap"
        :key="index">
        <p
          v-if="mapItem.title"
          class="title">
          {{ mapItem.title }}
        </p>
        <div class="table-content">
          <div
            v-for="item in mapItem.column"
            :key="item.label"
            class="table-tr "
            :class="{
              'disabled':item.disabled,
              'new': item.new,
            }">
            <div class="tr-title">
              <img
                v-if="item.type"
                class="field-type-icon"
                :src="getFieldTypeIcon(item.type, { highlight: item.disabled || item.new })">
              <tool-tip
                class="content"
                :data="item.label" />
            </div>
            <p class="tr-content">
              <span v-if="item.new">
                {{ t('待补充') }}
              </span>
              <span v-else>
                {{ item.value || '--' }}
              </span>
              <audit-icon
                v-if="item.new"
                class="new-tip"
                type="new" />
            </p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';

  import ToolTip from '@components/show-tooltips-text/index.vue';

  import getFieldTypeIcon from '@utils/getFieldTypeIcon';

  import type { ColumnType } from '../index.vue';

  interface Props {
    title: string,
    column: ColumnType[],
    inputFieldsMap?: Array<{
      title?: string,
      column:  ColumnType[]
    }>
  }
  defineProps<Props>();
  const { t } = useI18n();
</script>
<style scoped lang="postcss">
.strategy-upgrade-card {
  width: 491px;
  padding: var(--bk-theme-space-12) var(--bk-theme-space-16);
  background: var(--bk-theme-surface-default);
  border-radius: var(--bk-theme-tag-radius);
  box-shadow: var(--bk-theme-card-shadow);

  .field-type-icon {
    width: 46px;
    margin-right: var(--bk-theme-space-6);
  }

  .fields-map {
    margin-top: var(--bk-theme-space-16);
    font-size: 12px;
    color: var(--bk-theme-text-strong);

    .title {
      /* width: 459px; */
      height: 32px;
      padding-left: var(--bk-theme-space-8);
      margin-top: var(--bk-theme-space-12);
      font-size: 12px;
      line-height: 32px;
      color: var(--bk-theme-text-strong);
      background: var(--bk-theme-surface-muted);
    }
  }

  >.title {
    margin-bottom: var(--bk-theme-space-12);
    font-size: 14px;
    color: var(--bk-theme-text-strong);
  }

  .table-content {
    .table-tr:last-child {
      border-bottom: 1px solid var(--bk-theme-surface-muted);
    }

    .table-tr.disabled {
      color: var(--bk-theme-color-warn-2);

      .tr-title {
        color: var(--bk-theme-color-warn-2);

        .field-type-icon {
          width: 46px;
          margin-right: var(--bk-theme-space-6);
        }

        .content {
          text-decoration: line-through;
        }
      }

      .tr-content {
        color: var(--bk-theme-color-warn-2);
        text-decoration: line-through;
      }
    }

    .table-tr.new {
      color: var(--bk-theme-color-warn-2);

      .tr-title {
        color: var(--bk-theme-color-warn-2);

        .field-type-icon {
          width: 46px;
          margin-right: var(--bk-theme-space-6);
        }
      }

      .tr-content {
        position: relative;
        width: 100%;
        color: var(--bk-theme-color-warn-2);
      }

      .new-tip {
        position: absolute;
        top: 32%;
        right: 10px;
      }
    }

    .table-tr.highlight {
      .tr-title {
        color: var(--bk-theme-color-warn-2);
      }

      .tr-content {
        color: var(--bk-theme-color-warn-2);
      }
    }

    .table-tr {
      display: flex;
      align-items: center;
      height: 32px;
      border-top: 1px solid var(--bk-theme-surface-muted);

      >.tr-title {
        display: flex;
        height: 31px;
        max-width: 200px;
        min-width: 200px;
        padding: 0 var(--bk-theme-space-8);
        color: var(--bk-theme-text-weak);
        background: var(--bk-theme-table-header-bg);
        border-right: 1px solid var(--bk-theme-surface-muted);
        align-items: center;

        .tr-type {
          display: inline-block;
          width: 46px;
          height: 23px;
          margin-right: var(--bk-theme-space-8);
          font-size: 10px;
          font-weight: 400;
          line-height: 23px;
          color: var(--bk-theme-color-brand-2);
          text-align: center;
          background: var(--bk-theme-fill-selected);
          border-radius: var(--bk-theme-message-radius);
        }
      }

      >.tr-content {padding: var(--bk-theme-space-4) var(--bk-theme-space-8);
        color: var(--bk-theme-text-default);
      }
    }
  }
}
</style>
