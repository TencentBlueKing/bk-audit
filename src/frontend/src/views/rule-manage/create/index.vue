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
  <bk-loading :loading="listLoading || applicationLoading">
    <smart-action
      class="create-strategy-page">
      <div class="create-riskrule-main">
        <audit-form
          ref="formRef"
          class="strategt-form"
          :label-width="80"
          :model="formData"
          :rules="rules">
          <bk-form-item
            class="is-required mr16"
            :label="t('规则名称')"
            property="name">
            <bk-input
              v-model.trim="formData.name"
              :placeholder="t('请输入')"
              show-word-limit
              style="width: 480px;" />
          </bk-form-item>
          <bk-form-item
            class="is-required mr16"
            :label="t('适用范围')"
            property="scope">
            <div
              v-for="(item, index) in formData.scope"
              :key="index"
              class="condition-item">
              <div style="display: flex; width: 200px;flex: 1;">
                <span
                  v-if="index"
                  class="condition-equation bold"
                  style="width: 43px;margin-left: 0;border: 1px solid #c4c6cc;">
                  AND
                </span>
                <div
                  style="position: relative;flex: 1;">
                  <bk-form-item
                    class="mb0"
                    label=""
                    label-width="0"
                    :property="`scope.${index}.field`"
                    required>
                    <bk-select
                      v-model="item.field"
                      filterable
                      :input-search="false"
                      :placeholder="t('请选择')"
                      :search-placeholder="t('请输入关键字')"
                      @change="handleValueDicts">
                      <bk-option
                        v-for="(field, conditionIndex) in riskFieldList"
                        :key="conditionIndex"
                        :label="field.name"
                        :value="field.id" />
                    </bk-select>
                  </bk-form-item>
                </div>
              </div>
              <!-- 等式 -->
              <div>
                <bk-form-item
                  class="mb0"
                  label=""
                  label-width="0"
                  :property="`scope.${index}.operator`"
                  required>
                  <bk-select
                    v-model="item.operator"
                    class="condition-equation"
                    filterable
                    :placeholder="t('请选择')">
                    <bk-option
                      v-for="(operatorItem, valueIndex) in riskRuleOperatorList"
                      :key="valueIndex"
                      :label="operatorItem.name"
                      :value="operatorItem.id" />
                  </bk-select>
                </bk-form-item>
              </div>

              <!-- 值 -->
              <div
                class="value-box"
                style="flex: 1;"
                :style="styles[index]">
                <bk-form-item
                  class="mb0"
                  label=""
                  label-width="0"
                  :property="`scope.${index}.value`"
                  required
                  :rules="[
                    { message: '', trigger: 'change',validator: (value: Array<any>) => handleValidate(value) },
                  ]">
                  <!-- 策略id特殊处理 -->
                  <bk-select
                    v-if="item.field === 'strategy_id'"
                    v-model="item.value"
                    class="consition-value"
                    collapse-tags
                    filterable
                    :input-search="false"
                    :loading="strategyListLoading"
                    multiple
                    multiple-mode="tag">
                    <bk-option
                      v-for="sItem in strategyList"
                      :key="sItem.value"
                      :label="`${sItem.label} (${sItem.value})`"
                      :value="sItem.value" />
                  </bk-select>
                  <!-- operator特殊处理 -->
                  <audit-user-selector
                    v-else-if="item.field?.includes('operator')"
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
                    :list="[]"
                    :placeholder="t('请输入并Enter结束')"
                    trigger="focus"
                    @blur="isValueFocus[index] = false"
                    @focus="isValueFocus[index] = true" />
                </bk-form-item>
              </div>

              <!-- 添加 删除-->
              <div class="condition-icon">
                <div
                  v-if="formData.scope.length > 1"
                  v-bk-tooltips="t('删除')"
                  class="ml8"
                  @click="handleRemoveCondition(Number(index))">
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
            class="is-required mr16"
            :label="t('处理套餐')"
            property="pa_id">
            <div style="display: flex;align-items: center;">
              <bk-select
                v-model="formData.pa_id"
                filterable
                :placeholder="t('请选择')"
                style="width: 480px;"
                @change="handlePaIdChange">
                <bk-option
                  v-for="item in filterApplicationList"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id" />
              </bk-select>
              <router-link
                v-if="formData.pa_id"
                style="color: #979ba5;"
                target="_blank"
                :to="{
                  name:'applicationManageList',
                  query:{
                    id: formData.pa_id
                  }
                }">
                <audit-icon
                  v-bk-tooltips="t('查看套餐详情')"
                  class="ml8"
                  style="font-size: 16px;color: #979ba5;"
                  type="audit" />
              </router-link>
            </div>
          </bk-form-item>
          <bk-loading :loading="detailLoading">
            <bk-form-item
              v-if=" Object.keys(paramsDetailData)?.length"
              class="is-required mr16"
              :label="t('套餐参数')"
              property="pa_params">
              <div style="width: 976px;padding: 16px 12px;background: rgb(245 247 250 / 100%)">
                <template
                  v-for="(val,index) in Object.values(paramsDetailData)"
                  :key="`${val.key}-${index}`">
                  <bk-form-item
                    :label="val.name"
                    :label-width="150"
                    :property="`pa_params.${val.key}.field`"
                    required
                    style="margin-bottom: 16px;">
                    <bk-select
                      v-model="formData.pa_params[val.key].field"
                      filterable
                      :placeholder="t('请选择')"
                      style="width: 480px;">
                      <bk-option
                        v-for="(item, conditionIndex) in riskFieldList"
                        :key="conditionIndex"
                        :label="item.name"
                        :value="item.id" />
                    </bk-select>
                  </bk-form-item>
                </template>
              </div>
            </bk-form-item>
          </bk-loading>

          <bk-form-item
            class="mr16"
            label="">
            <bk-checkbox v-model="formData.auto_close_risk">
              <span style="font-size: 12px;">{{ t('套餐执行成功后自动关单') }}</span>
            </bk-checkbox>
          </bk-form-item>
        </audit-form>
      </div>
      <template #action>
        <bk-button
          class="w88"
          :loading="createLoading || updateLoading"
          style="margin-left: 80px;"
          theme="primary"
          @click="handleSubmit">
          {{ isEditMode ? t('保存') : t('提交') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </template>
    </smart-action>
  </bk-loading>
  <batch-dialog ref="batchDialogRef" />
</template>

<script setup lang='tsx'>
  // import { InfoBox } from 'bkui-vue';
  import _ from 'lodash';
  import {
    computed,
    reactive,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import ProcessApplicationManageService from '@service/process-application-manage';
  import RiskManageService from '@service/risk-manage';
  import RiskRuleManageService from '@service/rule-manage';
  import SoapManageService from '@service/soap-manage';
  import StrategyManageService from '@service/strategy-manage';

  import RiskRuleManageModel from '@model/risk-rule/rule-create';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useRouterBack from '@hooks/use-router-back';

  import BatchDialog from './components/dialog.vue';

  interface Errors{
    field: boolean,
    value: string[],
    operator: string,
  }
  const { t } = useI18n();
  const rules = {
    name: [
      {
        validator: (value: string) => !!value,
        message: t('规则名称不能为空'),
        trigger: 'blur',
      },
    ],
    pa_id: [
      {
        validator: (value: string) => !!value,
        message: t('处理套餐不能为空'),
        trigger: 'change',
      },
    ],
    pa_params: [
      {
        validator: (value: Record<string, any>) => Object.keys(value).length > 0
          && Object.values(value).every(item => !!item),
        message: t('套餐参数不能为空'),
        trigger: 'change',
      },
    ],
  };

  const router = useRouter();
  const route = useRoute();
  const { messageSuccess } = useMessage();


  const isValueFocus = reactive({} as Record<string, boolean>);
  const formData = ref(new RiskRuleManageModel());
  const formRef = ref();
  const batchDialogRef = ref();
  const errors = ref<Array<Errors>>([]);
  const lists = [{
    operator: '',
    field: '',
    value: [],
  }];
  formData.value.scope = lists;

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
  const filterApplicationList = computed(() => {
    const enableList = processApplicationList.value.filter(item => item.is_enabled);
    if (isEditMode) {
      const item = processApplicationList.value.find(item => item.id === formData.value.pa_id);
      if (item && !item.is_enabled) {
        return [
          item,
          ...enableList,
        ];
      }
    }
    return enableList;
  });

  const isEditMode = route.name === 'riskRuleEdit';
  const isCloneMode = route.name === 'riskRuleClone';


  const {
    run: fetchRuleList,
    loading: listLoading,
  } = useRequest(RiskRuleManageService.fetchRuleList, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 0,
    },
    onSuccess(data) {
      if (data.results.length) {
        [formData.value] = data.results;
        if (isCloneMode) {
          formData.value.name = `${formData.value.name}_copy`;
        }
        handleFetchDetail();
      }
    },
  });
  // 查看列表
  if (isEditMode || isCloneMode) {
    listLoading.value = true;
    fetchRuleList({
      page: 1,
      page_size: 1000,
      rule_id: route.params.id,
    });
  }
  // 获取所有策略列表
  const {
    run: fetchAllStrategyList,
    data: strategyList,
    loading: strategyListLoading,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    defaultValue: [],
  });
  // 获取处理套餐列表
  const {
    data: processApplicationList,
    loading: applicationLoading,
  } = useRequest(ProcessApplicationManageService.fetchApplicationsAll, {
    defaultValue: [],
    manual: true,
    onSuccess() {
      if (isEditMode || isCloneMode) {
        handleFetchDetail();
      }
    },
  });
  // 获取处理套餐详情
  const {
    run: fetchDetail,
    loading: detailLoading,
    data: paramsDetailData,
  } = useRequest(SoapManageService.fetchDetail, {
    defaultValue: {},
    onSuccess(data) {
      // 如果是新建 或者 pa_params为null
      if (!(isEditMode || isCloneMode) || !formData.value.pa_params) {
        formData.value.pa_params = {};
        Object.values(data).forEach((val) => {
          formData.value.pa_params[val.key] = {
            field: '',
          };
        });
      }
      if (isEditMode || isCloneMode) {
        formData.value.scope.forEach(({ field }:{field: string}) => {
          if (field === 'strategy_id' && !strategyList.value.length) {
            fetchAllStrategyList();
          }
        });
        // 防止新增字段取不到对应field
        Object.values(paramsDetailData.value).forEach((val) => {
          if (!formData.value.pa_params[val.key]) {
            formData.value.pa_params[val.key] = {
              field: '',
            };
          }
        });
      }
    },
  });
  //  获取风险可用字段
  const {
    data: riskFieldList,
  } = useRequest(RiskManageService.fetchFields, {
    defaultValue: [],
    manual: true,
  });


  const {
    run: create,
    loading: createLoading,
  } = useRequest(RiskRuleManageService.create, {
    defaultValue: null,
    onSuccess() {
      window.changeConfirm = false;
      batchDialogRef.value.show();
    },
  });
  const {
    run: update,
    loading: updateLoading,
  } = useRequest(RiskRuleManageService.update, {
    defaultValue: null,
    onSuccess() {
      window.changeConfirm = false;
      router.push({
        name: 'ruleManageList',
      });
      messageSuccess(t('编辑成功'));
    },
  });
  const {
    data: riskRuleOperatorList,
  } = useRequest(RiskRuleManageService.fetchRiskRuleOprators, {
    defaultValue: [],
    manual: true,
  });

  const handleValueDicts = (val: string) => {
    if (val === 'strategy_id' && !strategyList.value.length) {
      console.log(333);
      fetchAllStrategyList();
    }
  };
  const handleFetchDetail = () => {
    if (!processApplicationList.value.length || !formData.value.pa_id) return;
    const sopsTemplateId = processApplicationList.value
      .find(item => item.id === formData.value.pa_id)?.sops_template_id;
    if (sopsTemplateId) {
      fetchDetail({
        id: sopsTemplateId,
      });
    }
  };
  const handlePaIdChange = (id: string) => {
    if (id) {
      const sopsTemplateId = processApplicationList.value
        .find(item => item.id === id)?.sops_template_id;
      fetchDetail({
        id: sopsTemplateId,
      });
    } else {
      paramsDetailData.value = {};
      formData.value.pa_params = {};
    }
  };
  // 删除适用范围
  const handleRemoveCondition = (index: number) => {
    formData.value.scope.splice(index, 1);
    errors.value.splice(index, 1);
  };
  // 添加适用范围
  const handleAddCondition = () => {
    const item = {
      operator: '',
      field: '',
      value: [],
    };
    formData.value.scope.push(item);
  };
  const handleValidate = (value: any) => value.length > 0;
  const handleSubmit = () => {
    formRef.value.validate().then(() => {
      if (!isEditMode) {
        create(formData.value);
      } else {
        update(formData.value);
      }
    });
  };
  const handleCancel = () => {
    router.push({
      name: 'ruleManageList',
    });
  };
  useRouterBack(() => {
    router.push({
      name: 'ruleManageList',
    });
  });
</script>
<style scoped lang="postcss">
.create-strategy-page {
  padding: 28px 24px;
  background-color: #fff;

  .condition-item {
    display: flex;
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
      margin: 0 8px;

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
