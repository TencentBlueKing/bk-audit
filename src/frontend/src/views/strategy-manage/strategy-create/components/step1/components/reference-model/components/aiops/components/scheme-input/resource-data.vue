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
  <div class="strategy-aiops-resource-data-wrap">
    <bk-loading :loading="loading">
      <bk-form-item
        :label="sourceType === 'BuildIn' ? t('资产') : t('所属业务')"
        property="configs.data_source.result_table_id"
        style="margin-bottom: 12px;">
        <bk-cascader
          v-slot="{node,data}"
          v-model="formData.configs.data_source.result_table_id"
          :disabled="isEditMode || isCloneMode || isUpgradeMode"
          filterable
          id-key="value"
          :list="filterTableData"
          name-key="label"
          trigger="hover"
          @change="handleTableIdChange">
          <p
            v-bk-tooltips="{
              disabled: (node.children && node.children.length) || !data.leaf,
              content: sourceType === 'BuildIn'
                ? t('该系统暂未上报资源数据')
                : t('审计中心暂未获得该业务数据的使用授权，请联系系统管理员到BKBASE上申请权限'),
              delay: 400,
            }">
            {{ node.name }}
          </p>
        </bk-cascader>
      </bk-form-item>
      <span
        class="label-is-required"
        style="color: #63656e;">
        {{ t('输入字段映射') }}
      </span>
      <render-field
        ref="fieldRef"
        :configs="inputFields"
        :data="formData.configs.data_source.fields"
        :rt-fields="rtFields"
        :trigger-error="triggerError" />

      <!-- 方案参数 -->
      <div style="padding: 24px 0;">
        <span
          style="color: #63656e;">
          {{ t('方案参数') }}
        </span>
        <scheme-paramenters
          ref="paramenterRef"
          :control-detail="controlDetail" />
      </div>

      <!-- 多规则 -->
      <template
        v-for="(rule, ruleIndex) in formData.configs.rule_list"
        :key="ruleIndex">
        <auth-collapse-panel
          is-active
          :label="rule.rule_name"
          style="margin-bottom: 14px">
          <template #title>
            <div
              class="flex align-center justify-between"
              style="flex: 1;">
              <div class="flex align-center">
                <template v-if="editingRuleIndex === ruleIndex">
                  <bk-input
                    v-model="editingRuleName"
                    class="rule-name-input"
                    :maxlength="50"
                    :placeholder="t('请输入规则名称')"
                    style="width: 200px;"
                    @blur="handleSaveRuleName(ruleIndex)"
                    @keyup.enter="handleSaveRuleName(ruleIndex)"
                    @keyup.esc="handleCancelEditRuleName" />
                </template>
                <template v-else>
                  <span>{{ rule.rule_name }}</span>
                  <audit-icon
                    class="edit-icon"
                    style="margin-left: 16px; cursor: pointer;"
                    type="edit-fill"
                    @click.stop="handleStartEditRuleName(ruleIndex)" />
                </template>
              </div>
              <audit-icon
                class="delete-icon"
                :style="{
                  fontSize: '14px',
                  cursor: 'pointer',
                  visibility: formData.configs.rule_list.length === 1 ? 'hidden' : 'visible'
                }"
                type="delete"
                @click.stop="handleDeleteRule(ruleIndex)" />
            </div>
          </template>
          <div class="customize-rule">
            <div style="margin-top: 12px;">
              <span style="color: #63656e;">
                {{ t('筛选输入数据') }}
              </span>
              <filter-condition
                ref="filterRef"
                :data="rule.filter_config"
                :loading="tableRtFieldsLoading"
                :rt-fields="rtFields"
                :trigger-error="triggerError"
                @update-filter-config="handleUpdateFilterConfig" />
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
                  :selected="rule.risk_level === item.value"
                  @click="() => rule.risk_level = item.value">
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
                  v-model.trim="rule.risk_hazard"
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
                  v-model.trim="rule.risk_guidance"
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
                  v-model="rule.processor_groups"
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
                  v-model="rule.notice_groups"
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
            <!-- 规则描述 -->
            <div class="flex">
              <bk-form-item
                class="mr16"
                :label="t('规则描述')"
                label-width="160"
                property="rule_description"
                style="flex-basis: 50%;">
                <bk-input
                  v-model.trim="rule.rule_description"
                  autosize
                  :maxlength="1000"
                  :placeholder="t('请输入描述')"
                  show-word-limit
                  style="width: 100%;"
                  type="textarea" />
              </bk-form-item>
            </div>
          </div>
        </auth-collapse-panel>
      </template>
    </bk-loading>
  </div>
</template>

<script setup lang='ts'>
  import { InfoBox } from 'bkui-vue';
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import NoticeManageService from '@service/notice-group';
  import StrategyManageService from '@service/strategy-manage';

  import type ControlModel from '@model/control/control';
  import type AiopPlanModel from '@model/strategy/aiops-plan';
  import CommonDataModel from '@model/strategy/common-data';

  import useRequest from '@hooks/use-request';

  import SchemeParamenters from '../../components/scheme-paramenters/index.vue';
  import FilterCondition,  { type ConditionData } from '../components/filter-condition.vue';
  import RenderField from '../components/render-field.vue';

  type ItemType = {
    label: string,
    value: string
    config?: any;
  }

  interface Props {
    loading: boolean;
    tableData: Array<{
      label: string;
      value: string;
      children: Array<{
        label: string;
        value: string;
      }>
    }>;
    sourceType: string;
    inputFields: ValueOf<AiopPlanModel['input_fields']>;
    triggerError?: boolean,
    controlDetail: ControlModel;
  }
  interface Emits {
    (e: 'updateDataSource', value: FormData['data_source']): void,
  }
  interface Exposes{
    getValue: () => Promise<any>;
    getFields: () => Record<string, any>;
    setConfigs: (config: FormData) => void;
  }


  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const groupSelectRef = ref();
  let isInit = false;
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  // const outputFields = computed(() => props.controlDetail?.output_config[0]?.fields);
  const fieldRef = ref();
  const filterRef = ref();
  const editingRuleIndex = ref<number | null>(null);
  const editingRuleName = ref<string>('');
  const formData = ref({
    configs: {
      data_source: {
        fields: [] as ValueOf<AiopPlanModel['input_fields']>,
        filter_config: [] as ConditionData,
        result_table_id: [] as Array<string>,
      },
      rule_list: [{
        filter_config: [] as ConditionData,
        rule_name: '规则1',
        rule_description: '',
        risk_level: '',
        risk_hazard: '',
        risk_guidance: '',
        processor_groups: [],
        notice_groups: [],
      }],
    },
  });
  const filterTableData = computed(() => props.tableData.map(item => ({
    ...item,
    leaf: true,
    disabled: !(item.children && item.children.length),
  })));
  type FormData = typeof formData.value['configs'];
  if (!isEditMode && !isCloneMode && !isUpgradeMode)   {
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

  // 开始编辑规则名称
  const handleStartEditRuleName = (index: number) => {
    editingRuleIndex.value = index;
    editingRuleName.value = formData.value.configs.rule_list[index].rule_name;
    // 等待DOM更新后聚焦输入框
    nextTick(() => {
      const inputElement = document.querySelector('.rule-name-input input') as HTMLInputElement;
      if (inputElement) {
        inputElement.focus();
        inputElement.select();
      }
    });
  };

  // 保存规则名称
  const handleSaveRuleName = (index: number) => {
    if (editingRuleName.value.trim()) {
      formData.value.configs.rule_list[index].rule_name = editingRuleName.value.trim();
    }
    editingRuleIndex.value = null;
    editingRuleName.value = '';
  };

  // 取消编辑规则名称
  const handleCancelEditRuleName = () => {
    editingRuleIndex.value = null;
    editingRuleName.value = '';
  };

  // 删除规则
  const handleDeleteRule = (index: number) => {
    // 如果只有一个规则，不允许删除
    if (formData.value.configs.rule_list.length === 1) {
      return;
    }

    InfoBox({
      type: 'warning',
      title: t('确认删除规则'),
      subTitle: t('删除后将无法恢复，是否确认删除该规则？'),
      confirmText: t('删除'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm: () => {
        // 如果正在编辑被删除的规则，取消编辑状态
        if (editingRuleIndex.value === index) {
          handleCancelEditRuleName();
        } else if (editingRuleIndex.value !== null && editingRuleIndex.value > index) {
          // 如果正在编辑的规则在被删除规则之后，需要更新索引
          editingRuleIndex.value -= 1;
        }

        // 删除规则
        formData.value.configs.rule_list.splice(index, 1);
      },
    });
  };

  const {
    run: fetchTableRtFields,
    data: rtFields,
    loading: tableRtFieldsLoading,
  } = useRequest(StrategyManageService.fetchTableRtFields);


  const handleUpdateFilterConfig = (filterConfig: ConditionData) => {
    formData.value.configs.data_source.filter_config = filterConfig;
    handleUpdateDataSource();
  };
  const handleUpdateDataSource = () => {
    if (!isInit) return;
    emits('updateDataSource', formData.value.configs.data_source);
  };
  const handleTableIdChange = () => {
    fieldRef.value.clearFields();
    rtFields.value = [];
    const tableIdList = formData.value.configs.data_source.result_table_id;
    if (tableIdList.length) {
      fetchTableRtFields({
        table_id: tableIdList[tableIdList.length - 1],
      });
    }
    handleUpdateDataSource();
  };

  watch(() => props.inputFields, (data) => {
    if (data && (!isEditMode && !isCloneMode && !isUpgradeMode)) {
      formData.value.configs.data_source.fields = props.inputFields.map(item => item);
    }
  }, {
    immediate: true,
  });
  watch(() => props.tableData, (data) => {
    if (data) {
      formData.value.configs.data_source.result_table_id = [];
      handleUpdateDataSource();
      data.sort((a, b) => {
        if (a.children && a.children.length) return -1;
        if (b.children && b.children.length) return 1;
        return 0;
      });
    }
  }, {
    immediate: true,
  });
  defineExpose<Exposes>({
    getValue() {
      return Promise.all([fieldRef.value.getValue(), filterRef.value.getValue()]);
    },
    getFields() {
      return fieldRef.value.getFields();
    },
    setConfigs(config: Record<string, any>) {
      formData.value.configs.data_source.filter_config = config.data_source.filter_config;
      // 转换fields
      formData.value.configs.data_source.fields = props.inputFields.map((item) => {
        const sourceField = config.data_source.fields
          .find((field: {
            field_name: string;
            source_field: string
          }) => field.field_name === item.field_name)?.source_field || '';
        return { ...item, source_field: sourceField };
      });

      // 对tableid转换
      props.tableData.forEach((item) => {
        if (item.children && item.children.length) {
          item.children.forEach((cItem) => {
            if (cItem.value === config.data_source.result_table_id) {
              formData.value.configs.data_source.result_table_id = [item.value, config.data_source.result_table_id];
            }
          });
        }
      });
      isInit = true;
      filterRef.value.handleValueDicts(formData.value.configs.data_source.filter_config);
    },
  });
</script>


<style  lang="postcss" scoped>
.strategy-aiops-resource-data-wrap {
  .flex-center {
    display: flex;
    align-items: center;
  }

  .edit-icon {
    color: #979ba5;
    transition: color .2s;

    &:hover {
      color: #3a84ff;
    }
  }

  .delete-icon {
    color: #979ba5;
    transition: color .2s;

    &:hover {
      color: #ea3636;
    }
  }
}
</style>
