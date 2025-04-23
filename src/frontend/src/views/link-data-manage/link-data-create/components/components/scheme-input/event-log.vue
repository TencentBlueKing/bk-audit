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
          v-bk-tooltips="{
            disabled: !isDisabled,
            content: t('操作记录数据源需保持一致，请修改第一个操作记录数据源'),
          }"
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
                content: t('该系统暂未接入审计中心'),
                extCls:'event-log-unset-tooltips',
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
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CollectorManageService from '@service/collector-manage';
  import MetaManageService from '@service/meta-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  type ModelValue = LinkDataDetailModel['config']['links'][0]['left_table'] | LinkDataDetailModel['config']['links'][0]['right_table']

  interface Props {
    links: LinkDataDetailModel['config']['links'],
    linkIndex: number, // 第几个关联关系
    type: 'left' | 'right', // 左表还是右表
  }

  const props = defineProps<Props>();
  const modelValue = defineModel<ModelValue>({
    required: true,
  });
  const { t } = useI18n();
  const statusSystems = ref<Array<Record<string, any>>>([]);

  // 第一个关联中选中的Eventlog
  const firstSystemIds = computed(() => {
    if (props.linkIndex === 0 || props.type === 'right')  return [];
    const leftSystemIds = props.links[0].left_table.system_ids;
    const rightSystemIds = props.links[0].right_table.system_ids;
    if (leftSystemIds && leftSystemIds.length) {
      return leftSystemIds;
    } if (rightSystemIds && rightSystemIds.length) {
      return rightSystemIds;
    }
    return [];
  });

  const isDisabled = computed(() => firstSystemIds.value.length > 0);

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
      statusSystems.value.sort((a, b) => {
        if (a.status !== 'unset') return -1;
        if (b.status !== 'unset') return 1;
        return 0;
      });
    },
  });

  // 第二个关联开始，左表才有限制，必须选第一个关联中的表
  watch(() => firstSystemIds.value, (data) => {
    if (data.length) {
      modelValue.value.system_ids = data;
    }
  }, {
    immediate: true,
  });
</script>
<style>
.event-log-unset-tooltips {
  z-index: 9999 !important;
}
</style>


