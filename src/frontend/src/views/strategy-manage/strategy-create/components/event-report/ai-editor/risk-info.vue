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
  <div class="risk-info">
    <tdesign-list
      ref="tableRef"
      :border="false"
      :columns="columns"
      :data-source="dataSource"
      max-height="80vh"
      :need-empty-search-tip="false"
      :sync-pagination-to-url="false" />
  </div>
</template>

<script setup lang="tsx">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import TdesignList from '@components/tdesign-list/index.vue';

  import { execCopy } from '@utils/assist';

  // interface Props {
  // }

  interface Emits {
    (e: 'insert', value: string): void;
  }

  // const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const tableRef = ref();
  const dataSource = RiskManageService.fetchTodoRiskList;

  // 定义列配置
  const columns = computed(() => [
    {
      title: t('变量名称'),
      colKey: 'name',
      width: 200,
      cell: () => (
      <span>
        ID
      </span>
    ),
    },
    {
      title: t('应用方式'),
      colKey: 'name',
      width: 200,
      cell: (h: any, { row }: { row: { title: string } }) => (
      <span>
        {row.title}
        <audit-icon
          class="risk-info-copy-icon"
          onClick={() => handleCopy(row)}
          type="copy" />
      </span>

    ),
    },
    {
      title: t('变量说明'),
      colKey: 'name',
      width: 200,
      cell: () => (
      <span>
        fxxxxx
      </span>
    ),
    },
    {
      title: t('操作'),
      colKey: 'action',
      width: 100,
      cell: (h: any, { row }: { row: { title: string } }) => (
      <span
        class="insert-link"
        onClick={() => handleInsert(row)}>
        {t('插入')}
      </span>
    ),
    },
  ]);
  const handleCopy = (row: any) => {
    execCopy(row.title, t('复制成功'));
  };
  const handleInsert = (row: any) => {
    const variableText = `{{ risk }}${row.title}`;
    emits('insert', variableText);
  };

</script>

<style lang="postcss" scoped>
.risk-info {
  padding: 20px 40px 0;

  :deep(.t-table) {
    .insert-link {
      color: #3a84ff;
      cursor: pointer;
      transition: opacity .2s;

      &:hover {
        opacity: 80%;
      }
    }

    .risk-info-copy-icon {
      margin-left: 5px;
      color: #4d4f56;
      cursor: pointer;
      transition: color .2s;

      &:hover {
        color: #3a84ff;
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
