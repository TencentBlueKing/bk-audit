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
  <!-- <auth-collapse-panel
    is-active
    :label="t('方案配置')"
    style="margin-bottom: 14px;"> -->
  <div class="filter-conditon">
    <bk-form-item
      :label="t('检测条件')"
      label-width="160"
      property="configs.agg_condition"
      required>
      <!-- 条件下拉 -->
      <div
        v-for="(item, index) in formData.configs.agg_condition"
        :key="index"
        class="condition-item">
        <div style="display: flex;width: 200px;flex: 1;">
          <span
            v-if="index"
            v-bk-tooltips="t('点击切换')"
            class="condition-equation bold"
            style="width: 43px;margin-right: 8px;border: 1px solid #c4c6cc;"
            @click="handleTriggerLogicOp(item)">
            {{ item.condition.toUpperCase() }}
          </span>
          <div
            style="position: relative;flex: 1;">
            <bk-form-item
              class="mb0"
              error-display-type="tooltips"
              label=""
              label-width="0"
              :property="`configs.agg_condition.${index}.key`"
              required>
              <bk-select
                v-model="item.key"
                filterable
                :input-search="false"
                :placeholder="t('请选择')"
                :search-placeholder="t('请输入关键字')"
                @change="(value: string) => handleChangeCondition(value, index)">
                <bk-option
                  v-for="(condition, conditionIndex) in conditions"
                  :key="conditionIndex"
                  :label="condition.description"
                  :value="condition.field_name" />
              </bk-select>
            </bk-form-item>
          </div>
        </div>

        <!-- 等式 -->
        <div style="margin-left: 8px;">
          <bk-form-item
            class="mb0"
            error-display-type="tooltips"
            label=""
            label-width="0"
            :property="`configs.agg_condition.${index}.method`"
            required>
            <!-- 操作人账号特殊处理 -->
            <bk-input
              v-if="item.key==='user_identify_src_username'"
              v-model="item.method"
              class="condition-equation"
              :placeholder="t('请输入')" />
            <bk-select
              v-else
              v-model="item.method"
              class="condition-equation"
              filterable
              :placeholder="t('请选择')">
              <bk-option
                v-for="(operatorItem, valueIndex) in equations.strategy_operator"
                :key="valueIndex"
                :label="operatorItem.label"
                :value="operatorItem.value" />
            </bk-select>
          </bk-form-item>
        </div>

        <!-- 值 -->
        <div
          class="value-box"
          style="flex: 1; margin-left: 8px;"
          :style="styles[index]">
          <bk-form-item
            class="mb0"
            error-display-type="tooltips"
            label=""
            label-width="0"
            :property="`configs.agg_condition.${index}.value`"
            required
            :rules="[
              { message: '', trigger: ['change', 'blur'], validator: (value: Array<any>) => handleValidate(value) },
            ]">
            <bk-cascader
              v-if="dicts[item.key] && dicts[item.key].length"
              v-model="item.value"
              class="consition-value"
              collapse-tags
              filterable
              float-mode
              id-key="value"
              :list="dicts[item.key]"
              multiple
              name-key="label"
              trigger="hover"
              @blur="isValueFocus[index]=false"
              @focus="isValueFocus[index]=true" />
            <audit-user-selector
              v-else-if="item.key.includes('username')"
              v-model="item.value"
              allow-create
              class="consition-value" />
            <bk-tag-input
              v-else
              v-model="item.value"
              allow-create
              class="consition-value"
              collapse-tags
              :content-width="350"
              has-delete-icon
              :input-search="false"
              :list="dicts[item.key]"
              :loading="fieldLoading"
              :paste-fn="pasteFn"
              :placeholder="t('请输入并Enter结束')"
              trigger="focus"
              @blur="isValueFocus[index] = false"
              @focus="isValueFocus[index] = true" />
          </bk-form-item>
        </div>

        <!-- 添加 删除-->
        <div class="condition-icon">
          <div
            v-if="formData.configs.agg_condition.length > 1"
            v-bk-tooltips="t('删除(Remove)')"
            class="ml8"
            @click="handleRemoveCondition(index)">
            <audit-icon type="reduce-fill" />
          </div>
        </div>
      </div>
      <div
        style="width: 78px;"
        @click="handleAddCondition()">
        <bk-button
          text
          theme="primary">
          <audit-icon type="add" />
          {{ t('添加条件') }}
        </bk-button>
      </div>
    </bk-form-item>
    <bk-form-item
      :description="t('满足检测条件的操作记录的汇聚维度')"
      :label="t('统计字段')"
      label-width="160">
      <bk-select
        v-model="formData.configs.agg_dimension"
        class="not-select-close-btn"
        filterable
        :input-search="false"
        multiple
        multiple-mode="tag"
        :placeholder="t('请选择')"
        :search-placeholder="t('请输入关键字')"
        style="width: 480px;"
        @change="handleUpdateConfigs">
        <bk-option
          v-for="(condition, conditionIndex) in filterConditions"
          :key="conditionIndex"
          :label="condition.description"
          :value="condition.field_name" />
      </bk-select>
    </bk-form-item>
    <span class="form-item-title-required">
      {{ t('触发规则') }}
    </span>
    <div class="flex-center">
      <!-- <bk-form-item
        class="mb0"
        label=""
        label-width="160">
        <div
          class="rule-item">
          <span>{{ t('在') }}</span>
          <bk-form-item
            class="mb0"
            label=""
            label-width="0"
            property="configs.detects.time"
            required>
            <bk-time-picker
              ref="timerRef"
              v-model="formData.configs.detects.time"
              append-to-body
              :clearable="false"
              :has-footer="hasFooter"
              mode="horizontal"
              style="width: 160px;"
              type="timerange"
              @change="handleUpdateConfigs">
              <template #footer>
                <div class="custom-footer">
                  <bk-button
                    style="margin-left: auto;"
                    text
                    theme="primary"
                    @click="handleSuccess">
                    {{ t('确定') }}
                  </bk-button>
                </div>
              </template>
            </bk-time-picker>
          </bk-form-item>
          <span>{{ t('的时段内,') }}</span>
        </div>
      </bk-form-item> -->
      <bk-form-item
        class="content"
        label=""
        label-width="160"
        property="configs.agg_interval">
        <div
          class="rule-item"
          @mouseenter="isShowTip=true;"
          @mouseleave="isShowTip=false;">
          <span>{{ t('每') }}</span>
          <bk-form-item
            class="mb0"
            label=""
            label-width="0"
            style="position: relative">
            <bk-input
              v-model="formData.configs.agg_interval"
              class="form-item-common"
              :min="aggMin"
              :placeholder="t('请输入')"
              size="small"
              style="width: 80px;"
              type="number"
              @blur="handleUpdateConfigs" />
            <span
              v-bk-tooltips="{content: t('统计周期最小为5分钟'), placement: 'top'}"
              class="info-tip"
              :class="{'active':isShowTip}">
              <audit-icon
                type="alert" />
            </span>
          </bk-form-item>
          <bk-form-item
            class="mb0 ml8"
            label=""
            label-width="0">
            <bk-select
              v-model="timeType"
              class="bk-select"
              :clearable="false"
              size="small"
              style="width: 80px;">
              <bk-option
                v-for="(item, index) in timeTypes"
                :key="index"
                :label="t(item.name)"
                :value="item.id" />
            </bk-select>
          </bk-form-item>
          <span>{{ t('为一个统计周期,') }}</span>
        </div>
      </bk-form-item>
      <bk-form-item
        class="content"
        label=""
        label-width="160">
        <div
          class="rule-item"
          style="display: flex;">
          <span>{{ t('数据匹配次数') }}</span>
          <bk-form-item
            class="mb0"
            label=""
            label-width="0"
            property="configs.algorithms.method">
            <bk-select
              v-model="formData.configs.algorithms.method"
              class="bk-select"
              filterable
              :placeholder="t('请选择')"
              size="small"
              style="width: 120px;"
              @change="handleUpdateConfigs">
              <bk-option
                v-for="(item) in equations.algorithm_operator"
                :key="item.value"
                :label="item.label"
                :value="item.value" />
            </bk-select>
          </bk-form-item>
          <bk-form-item
            class="mb0 ml8"
            label=""
            label-width="0"
            property="configs.algorithms.threshold">
            <bk-input
              v-model="formData.configs.algorithms.threshold"
              :min="0"
              :placeholder="t('请输入')"
              :show-controls="false"
              size="small"
              style="width: 120px;"
              type="number"
              @blur="handleUpdateConfigs" />
          </bk-form-item>
        </div>
      </bk-form-item>
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
          :disabled="!!editData.risk_level"
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
  <!-- </auth-collapse-panel> -->
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    reactive,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import NoticeManageService from '@service/notice-group';
  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  type ItemType = {
    label: string,
    value: string
    config?: any;
  }

  interface Emits {
    (e: 'updateConfigs', value: IFormData['configs']): void,
  }
  interface Exposes {
    handleValueDicts: (data: conditionData) => void;
    setConfigs : (data: IFormData['configs']) => void;
  }
  interface Errors{
    condition: boolean,
    value: boolean,
    method: boolean,
    key: boolean,
  }
  interface IFormData{
    configs: {
      agg_condition: Record<string, any>[],
      agg_dimension: string[],
      algorithms: {
        method: string, // >=
        threshold: string|number, // 次数
      },
      detects: {
        time: ['00:00:00', '23:59:59'], // 开始
        count: number, // 次检测算法
        alert_window: number, // 触发条件周期
      },
      agg_interval: string|number,
      risk_level: string,
      risk_hazard: string,
      risk_guidance: string,
      notice_groups: Array<number>,
      processor_groups: Array<number>,
    },
  }
  interface DataType{
    label: string;
    value: string;
    children?: Array<DataType>;
  }
  defineProps<{
    editData: StrategyModel,
  }>();
  const emits = defineEmits<Emits>();
  const timeTypes = [
    {
      id: 'day',
      name: '天',
    },
    {
      id: 'hour',
      name: '小时',
    },
    {
      id: 'minute',
      name: '分钟',
    },
  ];
  const lists = [
    {
      condition: 'and', // AND / OR
      key: '', // 统计字段
      method: '', //  等式
      value: [] as Array<string>, // 对应值
    },
  ];

  const { t } = useI18n();
  const route = useRoute();
  const groupSelectRef = ref();
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const errors = ref<Array<Errors>>([]);
  // const timerRef = ref();
  const timeType = ref('minute');
  const dicts = ref<Record<string, Array<any>>>({});
  const isShowTip = ref(false);
  // const hasFooter = ref(true);
  const isValueFocus = reactive({} as Record<string, boolean>);

  type conditionData = typeof lists
  const formData = ref<IFormData>({
    configs: {
      agg_condition: [] as Record<string, any>[],
      agg_dimension: ['username'], // 默认选中操作人 且不可去掉
      algorithms: {
        method: '', // >=
        threshold: '' as string|number, // 次数
      },
      detects: {
        time: ['00:00:00', '23:59:59'], // 开始
        count: 1, // 次检测算法
        alert_window: 1, // 触发条件周期
      },
      agg_interval: 5 as string|number,
      risk_level: '',
      risk_hazard: '',
      risk_guidance: '',
      notice_groups: [],
      processor_groups: [],
    },
  });
  if (!isEditMode && !isCloneMode)   {
    formData.value.configs.agg_condition = lists;
    emits('updateConfigs', formData.value.configs);
  }
  const aggMin = computed(() => (timeType.value === 'minute' ? 5 : 0));
  const filterConditions = computed(() => conditions.value.filter(item => item.is_dimension));

  // eslint-disable-next-line vue/return-in-computed-property
  const styles = computed(() => {
    const styles = {} as Record<string, any>;
    if (!_.isEmpty(isValueFocus)) {
      Object.keys(isValueFocus).forEach((item) => {
        if (isValueFocus[item]) {
          styles[item] = { 'z-index': 999 };
        }
      });
    }
    return styles;
  });

  const riskLevelList = ref<Array<ItemType>>([]);
  const riskLevelTipMap: Record<'HIGH' | 'MIDDLE' | 'LOW', string> = {
    HIGH: t('问题存在影响范围很大或程度很深，或已导致重大错报、合规违规或资产损失风险，不处理可能产生更严重问题，需立即介入并优先处置'),
    MIDDLE: t('问题存在影响范围较大或程度较深，可能影响局部业务效率或安全性，需针对性制定措施并跟踪整改'),
    LOW: t('问题存在但影响范围有限，短期内不会对有重大问题，可通过常规流程优化解决'),
  };
  // 获取次数下拉
  const {
    loading: commonLoading,
    data: equations,
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

  // 筛选条件
  const {
    data: conditions,
  } = useRequest(StrategyManageService.fetchStrategyFields, {
    defaultValue: [],
    manual: true,
  });

  // 筛选条件值
  const {
    run: fetchStrategyFieldValue,
    loading: fieldLoading,
  } = useRequest(StrategyManageService.fetchStrategyFieldValue, {
    defaultValue: [],
  });

  const pasteFn = (value: string) => ([{ id: value, name: value }]);

  // 将数据转为秒
  const handleSeconds = () => {
    if (Number(formData.value.configs.agg_interval) % (60 * 60  * 24) === 0) {
      formData.value.configs.agg_interval = Number(formData.value.configs.agg_interval) / (60 * 60  * 24);
      timeType.value = 'day';
    } else if (Number(formData.value.configs.agg_interval) % (60 * 60) === 0) {
      formData.value.configs.agg_interval = Number(formData.value.configs.agg_interval) / (60 * 60);
      timeType.value = 'hour';
    }  else if (Number(formData.value.configs.agg_interval) % 60 === 0) {
      formData.value.configs.agg_interval = Number(formData.value.configs.agg_interval) / 60;
      timeType.value = 'minute';
    }
  };
  const handleAddCondition = () => {
    const item = {
      condition: 'and',
      key: '',
      method: '',
      value: [],
    };
    formData.value.configs.agg_condition.push(item);
  };
  const handleValidate = (value: any) => value.length > 0;
  // 切换and
  const handleTriggerLogicOp = (item: Record<string, any>) => {
    // eslint-disable-next-line no-param-reassign
    item.condition = item.condition === 'and' ? 'or' : 'and';
  };

  // 删除筛选条件
  const handleRemoveCondition = (index: number) => {
    formData.value.configs.agg_condition.splice(index, 1);
    errors.value.splice(index, 1);
  };
  // 切换筛选条件获取值
  const handleChangeCondition = (value:string, index: number) => {
    if (value) {
      fetchStrategyFieldValue({
        field_name: value,
      }).then((data) => {
        dicts.value[value] = data.filter((item: Record<string, any>) => item.id !== '');
      });
    }
    formData.value.configs.agg_condition[index].value = [];
  };

  const handleUpdateConfigs = () => {
    // 判断是否是级联
    const tmpCondition = formData.value.configs.agg_condition.map(item => ({
      ...item,
      value: dicts.value[item.key] && dicts.value[item.key].length
        ? item.value.map((valItem: Array<string>) => _.last(valItem))
        : item.value,
    }));
    emits('updateConfigs', {
      ...formData.value.configs,
      agg_condition: tmpCondition,
    });
  };

  // 回显下拉值
  const  handleValueDicts = (conditions: conditionData) => {
    conditions.forEach((item) => {
      dicts.value[item.key] = [];
    });
    Object.keys(dicts.value).forEach((key) => {
      if (key) {
        fetchStrategyFieldValue({
          field_name: key,
        }).then((data) => {
          dicts.value[key] = data;
          if (data && data.length) {
            handleCascader(key, data);
          }
        });
      }
    });
  };
  // 回显级联数据
  const handleCascader = (key: string, dataList: Array<DataType>) => {
    const conditionItemList = formData.value.configs.agg_condition.filter(el => el.key === key);
    if (!conditionItemList) return;

    conditionItemList.forEach((conditionItem) => {
      const valueMap = (conditionItem.value as Array<string>).reduce((res, v: string, index: number) => {
        res[v] = index;
        return res;
      }, {} as Record<string, number>);
      const newVal: Array<Array<string>> = [];
      dataList.forEach((data) => {
        if (valueMap[data.value] !== undefined) {
          newVal[valueMap[data.value]] = [data.value];
        } else {
          data.children?.forEach((childData: DataType) => {
            if (valueMap[childData.value] !== undefined) {
              newVal[valueMap[childData.value]] = [data.value, childData.value];
            }
          });
        }
      });
      // eslint-disable-next-line no-param-reassign
      conditionItem.value = newVal;
    });
  };

  watch(() => formData.value.configs.agg_condition, () => {
    handleUpdateConfigs();
  }, {
    deep: true,
  });


  defineExpose<Exposes>({
    handleValueDicts(data: conditionData) {
      handleValueDicts(data);
    },
    setConfigs(configs: IFormData['configs']) {
      formData.value.configs = {
        ...configs,
      };
      handleSeconds();
    },
  });
</script>
<style lang="postcss" scoped>
.custom-footer {
  display: flex;
  padding: 10px 20px;
}

.bk-select.not-select-close-btn {
  :deep(.bk-select-tag-wrapper) {
    .bk-tag-closable:nth-of-type(1) {
      .bk-tag-close {
        display: none !important;
      }
    }
  }

}

.filter-conditon {
  padding: 16px 0;

  .flex-center {
    display: flex;
    align-items: center;
  }


  .info-tip {
    position: absolute;
    top: 22%;
    right: 0;
    display: none;
    font-size: 16px;
    line-height: 1;
    color: #3a84ff;
  }

  .info-tip.active {
    display: inline-block;
  }

  .form-item-title-required {
    position: relative;
    font-weight: 400;
    color: #63656e;
  }

  .form-item-title-required::after {
    position: absolute;
    top: 0;
    width: 14px;
    color: #ea3636;
    text-align: center;
    content: '*';
  }

  .rule-item {
    display: flex;
    align-items: center;
    color: #63656e;

    :deep(.bk-form-label::after) {
      width: 0;
      content: '';
    }

    :deep(.bk-form-label) {
      padding-right: 0;
    }

    .mb0 {
      margin-bottom: 0;
    }

    .icon-hidden .icon-wrapper {
      display: none;
    }

    :deep(.bk-input,.bk-select,) {
      border-color: transparent;
      border-bottom-color: #c4c6cc;
    }

    :deep(.bk-date-picker-rel .bk-date-picker-editor) {
      border-color: transparent;
      border-bottom-color: #c4c6cc;
    }

    :deep(.bk-input--number-control) {
      display: none;
    }

    :deep(.bk-input.is-focused:not(is-readonly), .bk-select.is-focused:not(is-readonly)) {
      box-shadow: none;
    }
  }

  .condition-item {
    display: flex;

    /* grid-template-columns: repeat(4, auto);
    gap: 8px; */
    margin-bottom: 8px;
    justify-content: space-between;

    :deep(.bk-form-error) {
      display: none;
    }

    :deep(.bk-form-label::after) {
      width: 0;
      content: '';
    }

    :deep(.bk-form-label) {
      padding-right: 0;
    }

    .mb0 {
      margin-bottom: 0;
    }

    .bold {
      font-weight: bold;
    }

    .condition-equation {
      display: inline-block;
      width: 120px;
      height: 32px;

      /* margin: 0 8px; */

      /* font-weight: bold; */
      color: #3a84ff;
      text-align: center;
      background: #fff;
      border-radius: 2px;

      :deep(.bk-input--text) {
        color: #3a84ff;
      }
    }

    .value-box {
      position: relative;
      height: 32px;

      .consition-value {
        width: 560px;
      }
    }

    .condition-icon {
      display: flex;
      margin-left: 8px;
      font-size: 14px;
      color: #c4c6cc;
      cursor: pointer;
    }

    :deep(.is-errored .bk-input) {
      border: 1px solid red;
    }

    .error-icon {
      position: absolute;
      top: 10px;
      right: 8px;
      color: #ea3636;
    }

    :deep(.bk-form-item.is-error .bk-tag-input-trigger) {
      border-color: #ea3636;
    }
  }

}
</style>
