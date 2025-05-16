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
      property="configs.data_source.system_ids">
      <span>
        <bk-select
          v-model="systemIds"
          filterable
          :loading="isSystemListLoading"
          multiple
          multiple-mode="tag"
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择')"
          @change="handleChangeSystem">
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
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CollectorManageService from '@service/collector-manage';
  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  interface Expose {
    resetFormData: () => void,
    setConfigs: (config: Array<string>) => void;
  }

  interface Emits {
    (e: 'updateSystem', value: Array<string>): void,
  }

  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const systemIds = ref<Array<string>>([]);
  const statusSystems = ref<Array<Record<string, any>>>([]);

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

  // 选择系统
  const handleChangeSystem = () => {
    emits('updateSystem', systemIds.value);
  };

  defineExpose<Expose>({
    resetFormData: () => {
      systemIds.value = [];
    },
    setConfigs(ids: Array<string>) {
      systemIds.value = ids;
      emits('updateSystem', systemIds.value);
    },
  });
</script>
<style>
.event-log-unset-tooltips {
  z-index: 9999 !important;
}
</style>
