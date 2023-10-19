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
  <render-info-block>
    <bk-loading :loading="isSystemListLoading">
      <render-info-item :label="t('系统')">
        {{ systemIdList.map(item=>systemMap[item]).join(' , ') }}
      </render-info-item>
    </bk-loading>
  </render-info-block>
  <render-info-block>
    <render-info-item :label="t('输入字段映射')">
      <collapse-panel
        v-for="(item,index) in filterSystemIdList"
        :key="`${item}-${index}`"
        class="mb16"
        :is-active="isActive"
        :label="t(systemMap[item] || item)"
        style="background: #f5f7fa;">
        <bk-loading :loading="commonLoading || selectFieldsLoading || actionIdLoading || actionValueLoading">
          <multi-render-field
            v-if="data.configs.data_source?.fields[item]"
            :action-id-map="actionIdMap[item]"
            :action-id-to-value-map="actionIdToValueMap[item]"
            class="mb12"
            :configs="inputFields"
            :data="data.configs.data_source.fields[item]"
            :mapping-type-map="mappingTypeMap"
            :select-fields-map="selectRtFieldsMap"
            :system-id="item" />
        </bk-loading>
      </collapse-panel>
    </render-info-item>
  </render-info-block>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ControlManageService from '@service/control-manage';
  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import ControlModel from '@model/control/control';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import CollapsePanel from '@views/strategy-manage/strategy-create/components/aiops/components/components/collapse-panel.vue';

  import RenderInfoBlock from '../render-info-block.vue';
  import RenderInfoItem from '../render-info-item.vue';

  import MultiRenderField from './multi-render-field.vue';

  interface Props {
    data: StrategyModel,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const systemMap = ref<Record<string, string>>({});
  const mappingTypeMap = ref<Record<string, string>>({});
  const selectRtFieldsMap = ref<Record<string, string>>({});
  const systemIdList = computed(() => (props.data?.configs.data_source?.fields
    ? Object.keys(props.data?.configs.data_source.fields)
    : []));
  const filterSystemIdList = ref([] as string[]);
  const actionIdMap = ref<Record<string, Record<string, string>>>({});
  // systemid->actionid->fieldValue
  const actionIdToValueMap = ref<Record<string, any>>({});
  const inputFields = computed(() => {
    if (controlDetail.value.input_config && controlDetail.value.input_config.length) {
      return  controlDetail.value.input_config[0].require_fields || [];
    }
    return [];
  });
  const isActive = ref(true);

  // 获取系统
  const {
    loading: isSystemListLoading,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      data.forEach((item) => {
        systemMap.value[item.id] = item.name;
      });
    },
  });
  // 获取下拉列表的映射
  const {
    loading: selectFieldsLoading,
  } = useRequest(StrategyManageService.fetchStrategyFields, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      data.forEach((item) => {
        selectRtFieldsMap.value[item.field_name] = item.description;
      });
    },
  });
  // 获取策略通用字段
  const {
    loading: commonLoading,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: {
      mapping_type: [],
    },
    manual: true,
    onSuccess(data) {
      data.mapping_type.forEach((item) => {
        mappingTypeMap.value[item.value] = item.label;
      });
    },
  });
  // 获取actionID列表
  const {
    loading: actionIdLoading,
    run: fetchStrategyFieldValue,
  } = useRequest(StrategyManageService.fetchStrategyFieldValue, {
    defaultValue: [],
  });
  // 获取actionid 下的参数值
  const {
    run: fetchStrategyFields,
    loading: actionValueLoading,
  } = useRequest(StrategyManageService.fetchStrategyFields, {
    defaultValue: [],
  });
  // 获取方案详情
  const {
    run: fetchControlDetail,
    data: controlDetail,
  } = useRequest(ControlManageService.fetchControlDetail, {
    defaultValue: new ControlModel(),
    onSuccess() {
      if (props.data.configs.data_source) {
        const { fields } = props.data.configs.data_source;
        systemIdList.value.forEach((id) => {
          fields[id] = fields[id].map((fieldItem:Record<string, any>) => {
            const item = inputFields.value
              .find((item: { field_name: string }) => item.field_name === fieldItem.field_name);
            return {
              ...item,
              mapping_type: fieldItem.source_field[0]?.mapping_type,
              source_field: fieldItem.source_field,
            };
          });
        });
        filterSystemIdList.value = systemIdList.value.filter(id => fields[id] && fields[id].length);
      }
    },
  });
  watch(() => props.data, async (data) => {
    if (data) {
      fetchControlDetail({
        control_id: data.control_id,
        control_version: data.control_version,
      });
      if (data.configs.data_source) {
        for (const systemID of Object.keys(data.configs.data_source.fields)) {
          // 获取actionId的map对应
          const actionIdMapMemo: Record<string, any>  = {};
          fetchStrategyFieldValue({
            field_name: 'action_id',
            system_id: systemID,
          }).then((data) => {
            data?.forEach((item: { label: string; value: string }) => {
              actionIdMapMemo[item.value] = item.label;
            });
            actionIdMap.value[systemID] = actionIdMapMemo;
          });


          // actionID对应的source_field
          actionIdToValueMap.value[systemID] = {};
          if (props.data.configs.data_source) {
            const fields = props.data.configs.data_source.fields[systemID];

            fields.forEach((item) => {
              const sourceFields = item.source_field as Array<{
                action_id: string;
                source_field: string;
                mapping_type: string
              }>;
              sourceFields.forEach((item) => {
                actionIdToValueMap.value[systemID][item.action_id] = {};
                fetchStrategyFields({
                  action_id: item.action_id,
                  system_id: systemID,
                }).then((data) => {
                  actionIdToValueMap.value[systemID][item.action_id] = data;
                });
              });
            });
          }
        }
      }
    }
  }, {
    immediate: true,
  });
</script>
<!-- <style scoped>

</style> -->
