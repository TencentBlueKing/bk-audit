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
  <div class="strategy-customize-eventlog-wrap">
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.data_sheet_id"
      style="margin-bottom: 8px;">
      <span>
        <bk-select
          v-model="modelValue.rt_id"
          filterable
          :loading="loading"
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择')">
          <bk-option
            v-for="(dataSheet, dataSheetIndex) in tableData"
            :key="dataSheetIndex"
            :label="dataSheet.label"
            :value="dataSheet.value" />
        </bk-select>
      </span>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import { onMounted } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  type ModelValue = LinkDataDetailModel['config']['links'][0]['left_table'] | LinkDataDetailModel['config']['links'][0]['right_table']

  const modelValue = defineModel<ModelValue>({
    required: true,
  });
  const { t } = useI18n();

  // 获取rt_id
  const {
    data: tableData,
    run: fetchTable,
    loading,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });

  onMounted(() => {
    fetchTable({
      table_type: 'BizRt',
    });
  });
</script>
