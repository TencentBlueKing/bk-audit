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
  <div class="strategy-aiops-eventlog-wrap">
    <span
      class="label-is-required"
      style="color: #63656e;">
      {{ t('系统') }}
    </span>
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.system_id"
      style="margin-bottom: 12px;">
      <span>
        <bk-select
          v-model="formData.configs.data_source.system_id"
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
    <bk-loading :loading="loading">
      <span
        v-if="formData.configs.data_source.fields && Object.keys(formData.configs.data_source.fields).length"
        class="label-is-required"
        style="color: #63656e;">
        {{ t('输入字段映射') }}
      </span>
      <table-component
        v-for="systemId in Object.keys(formData.configs.data_source.fields)"
        :key="systemId"
        ref="tableRefs"
        :configs="inputFields"
        :data="formData.configs.data_source.fields[systemId]"
        :label="systemList.find(item=> item.id === systemId)?.name || ''"
        :system-id="systemId"
        :trigger-error="triggerError" />
    </bk-loading>
    <!-- 方案参数 -->
    <div style="padding-bottom: 24px;">
      <span
        style="color: #63656e;">
        {{ t('方案参数') }}
      </span>
      <scheme-paramenters
        ref="paramenterRef"
        :control-detail="controlDetail" />
    </div>
    <!-- 风险等级 -->
    <bk-form-item
      class="is-required risk-level-group"
      label=""
      label-width="160"
      property="risk_level">
      <template #label>
        <span
          v-bk-tooltips="{
            content: t('创建策略人工定义，标识和方便风险单快捷筛选，指引后续处理的跟进'),
            placement: 'top-start'
          }"
          style="
            color: #63656e;
            cursor: pointer;
            border-bottom: 1px dashed #979ba5;
          ">
          {{ t('风险等级') }}
        </span>
      </template>
      <bk-button-group>
        <bk-button
          v-for="item in riskLevelList"
          :key="item.value"
          :disabled="false"
          :loading="commonLoading"
          :selected="formData.configs.risk_level === item.value"
          @click="() => formData.configs.risk_level = item.value">
          <span
            v-bk-tooltips="{
              content: item.config.tips,
              extCls: 'strategy-way-tips',
              placement: 'top-start'
            }"
            style="
              line-height: 16px;
              border-bottom: 1px dashed #979ba5;
            ">
            {{ item.label }}
          </span>
        </bk-button>
      </bk-button-group>
    </bk-form-item>
    <!-- 风险危害和处理指引 -->
    <div class="flex">
      <bk-form-item
        class="mr16"
        :label="t('风险危害')"
        label-width="160"
        property="risk_hazard"
        style="flex: 1;">
        <bk-input
          v-model.trim="formData.configs.risk_hazard"
          autosize
          :maxlength="1000"
          :placeholder="t('请输入描述')"
          show-word-limit
          style="width: 100%;"
          type="textarea" />
      </bk-form-item>
      <bk-form-item
        :label="t('处理指引')"
        label-width="160"
        property="risk_guidance"
        style="flex: 1;">
        <bk-input
          v-model.trim="formData.configs.risk_guidance"
          autosize
          :maxlength="1000"
          :placeholder="t('请输入描述')"
          show-word-limit
          style="width: 100%;"
          type="textarea" />
      </bk-form-item>
    </div>
    <!-- 处理人 -->
    <bk-form-item
      class="is-required"
      :label="t('风险单处理人')"
      label-width="160"
      property="processor_groups"
      style="flex: 1;">
      <bk-loading
        :loading="isGroupLoading"
        style="width: 100%;">
        <bk-select
          ref="groupSelectRef"
          v-model="formData.configs.processor_groups"
          class="bk-select"
          filterable
          :input-search="false"
          multiple
          multiple-mode="tag"
          :placeholder="t('请选择通知组')"
          :popover-options="{
            zIndex: 1000
          }"
          :search-placeholder="t('请输入关键字')">
          <auth-option
            v-for="(item, index) in groupList"
            :key="index"
            action-id="list_notice_group"
            :label="item.name"
            :permission="checkResultMap.list_notice_group"
            :value="item.id" />
          <template #extension>
            <div class="create-notice-group">
              <auth-router-link
                action-id="create_notice_group"
                class="create_notice_group"
                target="_blank"
                :to="{
                  name: 'noticeGroupList',
                  query: {
                    create: true
                  }
                }">
                <audit-icon
                  style="font-size: 14px;color: #3a84ff;"
                  type="plus-circle" />
                {{ t('新增通知组') }}
              </auth-router-link>
            </div>
            <div
              class="refresh"
              @click="refreshGroupList">
              <audit-icon
                v-if="isGroupLoading"
                class="rotate-loading"
                svg
                type="loading" />
              <template v-else>
                <audit-icon
                  type="refresh" />
                {{ t('刷新') }}
              </template>
            </div>
          </template>
        </bk-select>
      </bk-loading>
    </bk-form-item>
    <!-- 关注人 -->
    <bk-form-item
      :label="t('关注人')"
      label-width="160"
      property="notice_groups"
      style="flex: 1;">
      <bk-loading
        :loading="isGroupLoading"
        style="width: 100%;">
        <bk-select
          ref="groupSelectRef"
          v-model="formData.configs.notice_groups"
          class="bk-select"
          filterable
          :input-search="false"
          multiple
          multiple-mode="tag"
          :placeholder="t('请选择通知组')"
          :popover-options="{
            zIndex: 1000
          }"
          :search-placeholder="t('请输入关键字')">
          <auth-option
            v-for="(item, index) in groupList"
            :key="index"
            action-id="list_notice_group"
            :label="item.name"
            :permission="checkResultMap.list_notice_group"
            :value="item.id" />
          <template #extension>
            <div class="create-notice-group">
              <auth-router-link
                action-id="create_notice_group"
                class="create_notice_group"
                target="_blank"
                :to="{
                  name: 'noticeGroupList',
                  query: {
                    create: true
                  }
                }">
                <audit-icon
                  style="font-size: 14px;color: #3a84ff;"
                  type="plus-circle" />
                {{ t('新增通知组') }}
              </auth-router-link>
            </div>
            <div
              class="refresh"
              @click="refreshGroupList">
              <audit-icon
                v-if="isGroupLoading"
                class="rotate-loading"
                svg
                type="loading" />
              <template v-else>
                <audit-icon
                  type="refresh" />
                {{ t('刷新') }}
              </template>
            </div>
          </template>
        </bk-select>
      </bk-loading>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import {
    // nextTick,
    ref,
    // computed,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import IamManageService from '@service/iam-manage';
  import MetaManageService from '@service/meta-manage';
  import NoticeManageService from '@service/notice-group';
  import StrategyManageService from '@service/strategy-manage';

  import type ControlModel from '@model/control/control';
  import type AiopPlanModel from '@model/strategy/aiops-plan';
  import CommonDataModel from '@model/strategy/common-data';

  import useRequest from '@hooks/use-request';

  import SchemeParamenters from '../../components/scheme-paramenters/index.vue';
  import TableComponent from '../components/render-table.vue';

  type ItemType = {
    label: string,
    value: string
    config?: any;
  }

  interface Props{
    loading: boolean;
    tableData: Array<{
      label: string;
      value: string;
      children: Array<{
        label: string;
        value: string;
      }>
    }>;
    inputFields: ValueOf<AiopPlanModel['input_fields']>;
    triggerError?:boolean,
    controlDetail: ControlModel;
  }
  interface Emits {
    (e: 'updateDataSource', value: IFormData['configs']['data_source']): void,
  }
  interface Exposes {
    getValue: () => Promise<any>;
    getFields: () => Record<string, Record<string, string>>;
    setConfigs: (data: IFormData['configs']) => void;
    clearData: () => void;
  }


  interface IFormData {
    configs: {
      data_source: {
        fields: Record<string, any>, // 字段映射
        system_id: string[],
        filter_config:[],
        result_table_id: string, // 结果表ID
      },
      risk_level: string,
      risk_hazard: string,
      risk_guidance: string,
      notice_groups: Array<number>,
      processor_groups: Array<number>,
    },
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const route = useRoute();
  const groupSelectRef = ref();
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  let isInit = false;
  let isInitFields = false;
  const { t } = useI18n();
  const tableRefs = ref();
  const formData = ref<IFormData>({
    configs: {
      data_source: {
        fields: {}, // 字段映射
        system_id: [],
        filter_config: [],
        result_table_id: '', // 结果表ID
      },
      risk_level: '',
      risk_hazard: '',
      risk_guidance: '',
      notice_groups: [],
      processor_groups: [],
    },
  });
  const statusSystems = ref<Array<Record<string, any>>>([]);

  if (!isEditMode && !isCloneMode && !isUpgradeMode) {
    isInit = true;
  }

  const riskLevelList = ref<Array<ItemType>>([]);
  const riskLevelTipMap: Record<'HIGH' | 'MIDDLE' | 'LOW', string> = {
    HIGH: t('问题存在影响范围很大或程度很深，或已导致重大错报、合规违规或资产损失风险，不处理可能产生更严重问题，需立即介入并优先处置'),
    MIDDLE: t('问题存在影响范围较大或程度较深，可能影响局部业务效率或安全性，需针对性制定措施并跟踪整改'),
    LOW: t('问题存在但影响范围有限，短期内不会对有重大问题，可通过常规流程优化解决'),
  };
  // 获取次数下拉
  const {
    loading: commonLoading,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess: (data) => {
      riskLevelList.value = data.risk_level.map(item => ({
        ...item,
        config: {
          tips: riskLevelTipMap[item.value as 'HIGH' | 'MIDDLE' | 'LOW'],
        },
      }));
    },
  });

  // 获取通知组权限
  const {
    data: checkResultMap,
  } = useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'list_notice_group',
    },
    defaultValue: {},
    manual: true,
  });

  const {
    loading: isGroupLoading,
    data: groupList,
    run: fetchGroupList,
  } = useRequest(NoticeManageService.fetchGroupSelectList, {
    defaultValue: [],
    manual: true,
  });

  const refreshGroupList = () => {
    groupList.value = [];
    groupSelectRef.value.searchKey = '';
    fetchGroupList();
  };

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
  const systemFieldsMap: Record<string, Array<Record<string, any>> | null> = {};
  // 选择系统
  const handleChangeSystem = (systemIdList: string[], needUpdate = true) => {
    isInitFields = true;
    Object.keys(systemFieldsMap).forEach((id) => {
      if (!systemIdList.includes(id)) {
        systemFieldsMap[id] = null;
      }
    });
    formData.value.configs.data_source.fields = systemIdList.reduce((result, systemId) => {
      if (formData.value.configs.data_source.fields[systemId]) {
        if (!systemFieldsMap[systemId]) {
          systemFieldsMap[systemId] = props.inputFields.map((item) => {
            const fItem = formData.value.configs.data_source.fields[systemId]
              .find(({ field_name: fieldName }: { field_name: string }) => fieldName === item.field_name);
            if (fItem) {
              return {
                ...item,
                mapping_type: fItem.mapping_type || fItem.source_field[0].mapping_type,
                source_field: fItem.source_field,
              };
            }
            return {
              ...item,
              source_field: [[]],
            };
          });
        }

        return {
          ...result,
          [systemId]: systemFieldsMap[systemId],
        };
      }
      return {
        ...result,
        [systemId]: props.inputFields.map(item => ({
          ...item,
          source_field: [[]],
        })),
      };
    }, {} as Record<string, any>);
    if (needUpdate) {
      handleUpdateConfigs();
    }
  };

  const handleUpdateConfigs = () => {
    if (!isInit) return;
    emits('updateDataSource', formData.value.configs.data_source);
  };

  watch(() => props.tableData, (data) => {
    if (data) {
      formData.value.configs.data_source.result_table_id = data[0]?.value;
      handleUpdateConfigs();
    }
  }, {
    immediate: true,
  });

  watch(() => props.inputFields, (data) => {
    if (data && data.length && !isInitFields && isInit) {
      handleChangeSystem(formData.value.configs.data_source.system_id);
    }
  }, {
    immediate: true,
  });
  defineExpose<Exposes>({
    getValue() {
      return Promise.all(tableRefs.value?.map((item: { getValue: () => Promise<any> }) => item.getValue()));
    },
    setConfigs(configs: IFormData['configs']) {
      formData.value.configs.data_source.fields = configs.data_source.fields;
      formData.value.configs.data_source.system_id = configs.data_source.system_id;
      if (props.inputFields && props.inputFields.length && !isInitFields) {
        handleChangeSystem(formData.value.configs.data_source.system_id);
      }
      isInit = true;
    },
    getFields() {
      const fields = (tableRefs.value as { getFields: () => Record<string, Record<string, string>> }[])
        .reduce((
          result,
          item,
        ) => {
          const list = item.getFields();
          return {
            ...result,
            ...list,
          };
        }, {} as Record<string, Record<string, string>>);
      return fields;
    },
    clearData() {
      if (formData.value.configs.data_source.system_id && formData.value.configs.data_source.system_id.length) {
        formData.value.configs.data_source.system_id = [];
        handleChangeSystem([]);
      }
    },
  });
</script>
<!-- <style lang="postcss">
</style> -->
<style>
.event-log-unset-tooltips {
  z-index: 9999 !important;
}
</style>

