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

    <tdesign-list
      ref="tableRef"
      :border="false"
      :columns="columns"
      :data-source="dataSource"
      :need-empty-search-tip="false" />
  </div>
</template>

<script setup lang="tsx">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import TdesignList from '@components/tdesign-list/index.vue';

  // interface Props {
  // }

  // interface Emits {
  //   (e: 'insert', value: string): void;
  // }

  // const props = defineProps<Props>();
  // const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const tableRef = ref();
  const variableList = ref<any[]>([]);

  // 定义列配置
  const columns = computed(() => [
    {
      title: t('字段名称'),
      colKey: 'field_name',
      width: 200,
    },
    {
      title: t('字段显示名'),
      colKey: 'display_name',
      width: 200,
    },
  ]);

  // 数据源函数
  const dataSource = async (params: any) =>
    // TODO: 替换为实际的数据获取接口
    // 目前返回静态数据，实际使用时需要调用对应的API
    // eslint-disable-next-line implicit-arrow-linebreak
    ({
      results: variableList.value,
      total: variableList.value.length,
      page: params.page || 1,
      num_pages: 1,
    })
  ;

  // const handleInsert = (row: any) => {
  //   const variableText = `{{ event.${row.field_name} }}`;
  //   emits('insert', variableText);
  // };
</script>

<style lang="postcss" scoped>
.event-info {
  .tips-banner {
    display: flex;
    align-items: flex-start;
    padding: 12px 16px;
    margin-bottom: 16px;
    background: #f0f5ff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;

    .info-icon {
      margin-top: 2px;
      margin-right: 8px;
      font-size: 14px;
      color: #3a84ff;
      flex-shrink: 0;
    }

    .tips-text {
      font-size: 12px;
      line-height: 20px;
      color: #4d4f56;
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
</style>

