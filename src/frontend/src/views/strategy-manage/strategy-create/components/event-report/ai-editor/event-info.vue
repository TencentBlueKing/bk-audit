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
  <div class="event-info">
    <div class="tips-banner">
      <audit-icon
        class="info-icon"
        type="info-fill" />
      <span class="tips-text">
        {{ t('一个审计风险工单可能关联多条事件,可以使用聚合函数对数据进行处理;若不使用聚合函数,系统将默认提取最后一个事件的数据') }}
      </span>
    </div>
    <div class="event-info-table">
      <div class="table-header">
        <div class="table-cell header-cell table-cell-right-border w1">
          {{ t('变量名称') }}
        </div>
        <div class="table-cell header-cell table-cell-right-border w2">
          {{ t('聚合函数') }}
        </div>
        <div class="table-cell header-cell table-cell-right-border w3">
          {{ t('引用方式') }}
        </div>
        <div class="table-cell header-cell table-cell-right-border w4">
          {{ t('变量说明') }}
        </div>
        <div class="table-cell header-cell w5">
          {{ t('操作') }}
        </div>
      </div>
      <div
        v-for="(row, index) in tableData"
        :key="index"
        class="table-row">
        <div class="table-cell table-cell-right-border w1">
          {{ row.name }}
        </div>

        <div class="table-cell table-cell-right-border w2 pn">
          <bk-select
            v-model="row.aggregation"
            class="event-info-aggregation-select">
            <bk-option
              v-for="item in aggregationLists"
              :id="item.value"
              :key="item.value"
              :name="item.label" />
          </bk-select>
        </div>
        <div class="table-cell table-cell-right-border w3">
          <span>{{ row.reference }}</span>
          <audit-icon
            class="copy-icon"
            type="copy"
            @click="handleCopy(row.reference)" />
        </div>
        <div class="table-cell table-cell-right-border w4">
          {{ row.description }}
        </div>
        <div class="table-cell w5">
          <span
            class="insert-link"
            @click="handleInsert(row.reference)">
            {{ t('插入') }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="tsx">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { execCopy } from '@utils/assist';

  interface Emits {
    (e: 'insert', value: string): void;
  }

  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  // 表格数据
  const tableData = ref([
    {
      name: '责任人',
      aggregation: '1',
      reference: '{{ event.operator }}',
      description: '-',
    },
    {
      name: '账号',
      aggregation: '2',
      reference: '{{ latest(event.account)}}',
      description: '-',
    },
  ]);

  // 聚合函数
  const aggregationLists = ref([
    {
      label: '不聚合',
      value: '1',
    },
    {
      label: 'latest（取最新事件值）',
      value: '2',
    },
  ]);

  // 复制
  const handleCopy = (text: string) => {
    execCopy(text, t('复制成功'));
  };
  // 插入
  const handleInsert = (reference: string) => {
    emits('insert', reference);
  };

</script>

<style lang="postcss" scoped>
.event-info {
  .tips-banner {
    display: flex;
    width: 880px;
    height: 32px;
    padding: 0 9px;
    margin: 24px 0 0 40px;
    line-height: 32px;
    background: #f0f5ff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;
    align-items: center;

    .info-icon {
      font-size: 14px;
      color: #3a84ff;
    }

    .tips-text {
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
    }
  }

  .event-info-table {
    margin: 24px 40px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
    border-radius: 2px;

    .table-header {
      display: flex;
      background: #f0f1f5;
      border-bottom: 1px solid #dcdee5;
    }

    .table-row {
      display: flex;
      border-bottom: 1px solid #dcdee5;
      transition: background-color .2s;

      &:last-child {
        border-bottom: none;
      }

      &:hover {
        background: #f5f7fa;
      }
    }

    .table-cell {
      display: flex;
      height: 42px;
      padding-left: 16px;
      font-size: 12px;
      color: #4d4f56;
      align-items: center;
      flex-shrink: 0;

      &.header-cell {
        font-weight: 500;
        color: #313238;
      }

      &.table-cell-right-border {
        border-right: 1px solid #dcdee5;
      }

      &.w1 {
        width: 164px;
      }

      &.w2 {
        width: 201px;
      }

      &.w3 {
        width: 237px;
      }

      &.w4 {
        width: 148px;
      }

      &.w5 {
        width: 100px;
      }

      &.pn {
        padding: 0;
      }

      .copy-icon,
      .expand-icon {
        font-size: 14px;
        cursor: pointer;
        transition: color .2s;
      }

      .copy-icon {
        margin-left: 5px;
        color: #4d4f56;

        &:hover {
          color: #3a84ff;
        }
      }

      .expand-icon {
        color: #979ba5;
      }

      .insert-link {
        color: #3a84ff;
        cursor: pointer;
        transition: opacity .2s;

        &:hover {
          opacity: 80%;
        }
      }
    }
  }

  :deep(.t-table) {
    .reference-cell {
      display: flex;
      align-items: center;
      gap: 8px;

      .copy-icon {
        font-size: 14px;
        color: #3a84ff;
        cursor: pointer;
        transition: opacity .2s;

        &:hover {
          opacity: 80%;
        }
      }
    }

    .insert-link {
      color: #3a84ff;
      cursor: pointer;
      transition: opacity .2s;

      &:hover {
        opacity: 80%;
      }
    }
  }

  .footer-tips {
    padding-top: 16px;
    margin-top: 16px;
    border-top: 1px solid #e8e8e8;

    .tip-item {
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;

      &:last-child {
        margin-bottom: 0;
      }
    }
  }
}

.empty-text {
  padding: 20px;
  font-size: 14px;
  color: #979ba5;
  text-align: center;
}

.event-info-aggregation-select {
  :deep(.bk-input) {
    width: 201px;
    height: 42px;
    border: none;
  }
}
</style>

