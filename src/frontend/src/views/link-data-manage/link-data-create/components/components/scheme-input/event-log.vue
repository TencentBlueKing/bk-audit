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
      property="system_ids"
      style="margin-bottom: 8px;">
      <span>
        <bk-select
          v-model="modelValue.system_ids"
          collapse-tags
          :disabled="isDisabled"
          filterable
          :loading="isSystemListLoading"
          multiple
          multiple-mode="tag"
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择')">
          <bk-option
            v-for="(system, systemIndex) in statusSystems"
            :key="systemIndex"
            :disabled="system.status == 'unset'"
            :label="system.name"
            :value="system.id">
            <span
              v-bk-tooltips="{
                disabled: system.status != 'unset',
                content: t('该系统暂未接入审计中心')
              }"
              style=" display: inline-block;width: 100%;">
              {{ system.name }}
            </span>
          </bk-option>
        </bk-select>
      </span>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CollectorManageService from '@service/collector-manage';
  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  type ModelValue = LinkDataDetailModel['config']['links'][0]['left_table'] | LinkDataDetailModel['config']['links'][0]['right_table']

  interface Props {
    links: LinkDataDetailModel['config']['links']
  }

  const props = defineProps<Props>();
  const modelValue = defineModel<ModelValue>({
    required: true,
  });
  const { t } = useI18n();
  const statusSystems = ref<Array<Record<string, any>>>([]);

  const firstSystemIds = computed(() => {
    if (props.links.length > 1) {
      const leftSystemIds = props.links[0].left_table.system_ids;
      const rightSystemIds = props.links[0].right_table.system_ids;
      if (leftSystemIds && leftSystemIds.length) {
        return leftSystemIds;
      } if (rightSystemIds && rightSystemIds.length) {
        return rightSystemIds;
      }
      return [];
    }
    return [];
  });

  const isDisabled = computed(() => firstSystemIds.value.length > 0);

  // 获取rt_id
  const {
    data: tableData,
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
    onSuccess: () => {
      // EventLog 默认使用第一个rt_id（只有一个）
      // 额外传递system_ids参数，只有EventLog才需要
      modelValue.value.rt_id = tableData.value[0]?.value;
    },
  });

  // 获取系统
  const {
    loading: isSystemListLoading,
    data: systemList,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      const ids = data.map(item => item.id).join(',');
      fetchBatchSystemCollectorStatusList({
        system_ids: ids,
      });
    },
  });

  // 批量获取系统状态
  const {
    run: fetchBatchSystemCollectorStatusList,
  } = useRequest(CollectorManageService.fetchBatchSystemCollectorStatusList, {
    defaultValue: null,
    onSuccess: (result) => {
      if (!result) {
        return;
      }
      statusSystems.value = systemList.value.map(item => ({
        id: item.id,
        name: item.name,
        status: result[item.id].status,
      }));
      if (isDisabled.value) {
        modelValue.value.system_ids = firstSystemIds.value;
      }
      statusSystems.value.sort((a, b) => {
        if (a.status !== 'unset') return -1;
        if (b.status !== 'unset') return 1;
        return 0;
      });
    },
  });

  onMounted(() => {
    fetchTable({
      table_type: 'EventLog',
    });
  });
</script>


