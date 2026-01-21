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
  <div class="risk-await-deal-wrap">
    <audit-form
      ref="formRef"
      form-type="vertical"
      :model="formData"
      :rules="rules">
      <bk-form-item
        :label="t('处理方法')"
        required>
        <bk-radio-group
          :model-value="formData.method"
          @change="handleChangeMethod">
          <bk-radio
            v-for="item in radioGroup"
            :key="item.id"
            :label="item.id">
            {{ t(item.name) }}
          </bk-radio>
        </bk-radio-group>
      </bk-form-item>

      <!-- 人工关单 -->
      <template v-if="formData.method === 'closeOrder'">
        <bk-form-item
          :label="t('处理说明')"
          property="description"
          required>
          <rich-editor
            ref="richEditor"
            v-model:content="formData.description"
            :default="formData.description"
            :max-len="1000" />
        </bk-form-item>
      </template>
      <!-- 转单 -->
      <template v-else-if="formData.method === 'transfer'">
        <bk-form-item
          :label="t('转单人员')"
          property="new_operators"
          required>
          <audit-user-selector
            v-model="formData.new_operators"
            :placeholder="t('请输入人员')" />
        </bk-form-item>
        <bk-form-item
          :label="t('处理说明')"
          property="description"
          required>
          <rich-editor
            ref="richEditor"
            v-model:content="formData.description"
            :default="formData.description"
            :max-len="1000" />
        </bk-form-item>
      </template>

      <!-- 处理套餐 -->
      <template v-else-if="formData.method === 'ProcessPackage'">
        <bk-form-item
          class="is-required"
          :label="t('处理套餐')"
          property="pa_id">
          <bk-select
            v-model="formData.pa_id"
            filterable
            :loading="applicationLoading"
            :placeholder="t('请选择')"
            @change="handlePaIdChange">
            <bk-option
              v-for="item in filterProcessApplicationList"
              :key="item.id"
              :label="item.name"
              :value="item.id" />
          </bk-select>
        </bk-form-item>
        <bk-loading :loading="detailLoading">
          <bk-form-item
            v-if="Object.keys(paramsDetailData)?.length"
            class="is-required"
            :label="t('套餐参数')"
            property="pa_params">
            <div style="padding: 16px 12px;background: rgb(245 247 250 / 100%)">
              <template
                v-for="(val, index) in Object.values(sortByIndex (paramsDetailData))"
                :key="`${val.key}-${index}`">
                <!-- 只显示需要显示的字段 -->
                <bk-form-item
                  v-if="val.show_type === 'show' && !val.is_hide"
                  :label="val.name"
                  :label-width="300"
                  :property="`pa_params.${val.key}`"
                  required
                  :rules="[
                    { message: t('不能为空'), trigger: 'change', validator: (value: any) => handlePaValidate(value) },
                  ]"
                  style="margin-bottom: 16px;">
                  <application-parameter
                    v-model="formData.pa_params[val.key]"
                    clearable
                    :config="val"
                    :detail-data="detailData"
                    :event-data-list="eventDataList"
                    :risk-field-list="riskFieldList" />
                  <template #error="message">
                    <div>{{ val.name }}{{ message }}</div>
                  </template>
                  <template #label>
                    <div
                      class="val-label">
                      <span
                        v-bk-tooltips="{
                          content: t(val.desc),
                          disabled: val.desc === '',
                        }"
                        :class="val.desc === '' ? 'label-name' : 'label-name underline'">{{ val.name }} </span>
                      <bk-dropdown
                        v-if="val.custom_type === 'datetime' || val.custom_type === 'textarea'
                          || val.custom_type === 'input' || val.custom_type === 'bk_date_picker'
                          || val.custom_type === ''"

                        ref="dropdownRef"
                        :is-show="val.dropdownShow"
                        trigger="hover">
                        <span
                          class="label-text"
                          @click="handleShow(val)">{{ typeText(val?.type) }} <audit-icon
                            class="line-down"
                            type="angle-line-down" /></span>
                        <template #content>
                          <bk-dropdown-menu>
                            <bk-dropdown-item
                              v-for="item in dropdownList"
                              :key="item.id"
                              @click="handleClick(item, val)">
                              {{ item.name }}
                            </bk-dropdown-item>
                          </bk-dropdown-menu>
                        </template>
                      </bk-dropdown>
                    </div>
                  </template>
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
      </template>
      <bk-form-item label="">
        <auth-button
          action-id="edit_risk_v2"
          :loading="loading"
          :permission="detailData.permission.process_risk || detailData.current_operator.includes(userInfo.username)"
          :resource="detailData.risk_id"
          style="min-width: 72px;"
          theme="primary"
          @click="handleSubmit">
          {{ t('提交') }}
        </auth-button>
        <bk-button
          style="min-width: 72px;margin-left: 8px;"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </bk-form-item>
    </audit-form>
  </div>
</template>

<script setup lang='ts'>
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import ProcessApplicationManageService from '@service/process-application-manage';
  import RiskManageService from '@service/risk-manage';
  import SoapManageService from '@service/soap-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import ApplicationParameter from '@components/application-parameter/index.vue';
  import RichEditor from '@components/editor/index.vue';

  interface Props {
    riskId: string,
    detailData: RiskManageModel,
    userInfo: {
      username: string,
    },
    eventDataList: Record<string, any>[],
  }

  interface Emits{
    (e:'update'): void,
  }

  interface ParamItem {
    custom_type: string;
    desc:string;
    form_schema: Record<string, any>;
    index: number;
    key: string;
    name: string;
    show_type: string;
    source_info: Record<string, any>;
    source_tag: string;
    source_type: string;
    validation: string;
    is_condition_hide: boolean | string;
    pre_render_mako: boolean;
    value: string;
    version: string;
    is_meta: boolean;
    schema: Record<string, any>;
    dropdownShow?: boolean;
    type?: string | undefined;
    is_hide?: boolean | undefined;
    default_value?: any;
    hide_condition?: any[]; // 添加缺失的hide_condition属性
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { messageSuccess } = useMessage();
  const typeText = (val: string | undefined) => (val === 'self' ?  t('自定义输入') : t('字段值引用'));
  const handleShow = (val:ParamItem) => {
    Object.keys(paramsDetailData.value).forEach((obj) => {
      if (obj  === val.key) {
        paramsDetailData.value[obj].dropdownShow = true;
      }
    });
  };
  const dropdownList = ref([
    {
      id: 'self',
      name: t('自定义输入'),
    },
    {
      id: 'field',
      name: t('字段值引用'),
    },
  ]);
  const rules = {
    new_operators: [{
      validator: (value: string) => !!value && value.length > 0,
      trigger: 'change',
      message: t('转单人不能为空'),
    }],
    description: [{
      validator: (value: string) => !!value,
      trigger: 'change',
      message: t('说明不能为空'),
    }],
    pa_id: [{
      validator: (value: string) => !!value,
      trigger: 'change',
      message: t('处理套餐不能为空'),
    }],
    pa_params: [
      {
        validator: (value: Record<string, any>) => Object.keys(value).length > 0
          && Object.values(value).every(item => !!item),
        message: t('套餐参数不能为空'),
        trigger: 'change',
      },
    ],
  };
  const radioGroup = [
    {
      id: 'closeOrder',
      name: t('人工关单'),
    },
    {
      id: 'transfer',
      name: t('转单'),
    },
    {
      id: 'ProcessPackage',
      name: t('处理套餐'),
    },
  ];

  const formData = ref<Record<string, any>>({
    method: 'closeOrder',
    risk_id: props.riskId,
  });
  const formRef = ref();
  const loading = computed(() => transLoading.value || autoProcessLoading.value || closeLoading.value);
  const filterProcessApplicationList = computed(() => processApplicationList.value
    .filter(item => item.is_enabled));

  const dropdownRef = ref();
  const handleClick = (label: Record<string, any>, item: ParamItem) => {
    Object.keys(paramsDetailData.value).forEach((obj) => {
      if (obj  === item.key) {
        paramsDetailData.value[obj].type = label.id;
        paramsDetailData.value[obj].dropdownShow = false;
      }
    });
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

  const handlePaValidate = (value: {field: string, value: string}) => {
    if (!value || typeof value !== 'object') return false;
    const { field, value: val } = value;
    // 检查field和value是否都为空（包括undefined、null、空字符串、）
    const isFieldEmpty = field === undefined || field === null || field === '';
    const isValueEmpty = val === undefined || val === null || val === '' ;
    // 只有当field和value都为空时才返回false，否则返回true
    return !(isFieldEmpty && isValueEmpty);
  };

  //  获取风险可用字段
  const {
    data: riskFieldList,
  } = useRequest(RiskManageService.fetchFields, {
    defaultValue: [],
    manual: true,
  });
  // 获取处理套餐列表
  const {
    data: processApplicationList,
    loading: applicationLoading,
  } = useRequest(ProcessApplicationManageService.fetchApplicationsAll, {
    defaultValue: [],
    manual: true,
  });
  // 获取处理套餐详情
  const sortByIndex = (obj: Record<string, ParamItem>) => {
    const sortedKeys = Object.keys(obj).sort((a, b) => obj[a].index - obj[b].index);

    return sortedKeys.reduce((acc, key) => {
      acc[key] = obj[key];
      return acc;
    }, {} as Record<string, ParamItem>);
  };
  const paramsDetailData = ref<Record<string, ParamItem>>({});
  const {
    run: fetchDetail,
    loading: detailLoading,
  } = useRequest(SoapManageService.fetchDetail, {
    defaultValue: {},
    onSuccess(data) {
      // 给对象中的每一项添加 type: 'self',
      Object.keys(data).forEach((key) => {
        // eslint-disable-next-line no-param-reassign
        data[key].type = 'self';
        // eslint-disable-next-line no-param-reassign
        data[key].dropdownShow = false;
        // eslint-disable-next-line no-param-reassign
        data[key].is_hide = false;
      });
      paramsDetailData.value = data;
      // 如果是新建 或者 pa_params为null
      formData.value.pa_params = {};
      Object.values(data).forEach((val) => {
        formData.value.pa_params[val.key] = {
          field: '',
          value: '', // 添加填写字段
        };
      });
    },
  });

  // 人工执行处理套餐
  const {
    run: autoProcess,
    loading: autoProcessLoading,
  } = useRequest(RiskManageService.autoProcess, {
    defaultValue: null,
    onSuccess() {
      // retToList();
      emits('update');
      messageSuccess(t('人工处理提交处理套餐成功'));
    },
  });
  // 人工关单
  const {
    run: close,
    loading: closeLoading,
  } = useRequest(RiskManageService.close, {
    defaultValue: null,
    onSuccess() {
      emits('update');
      messageSuccess(t('人工关单成功'));
    },
  });
  // 人工转单
  const {
    run: transRisk,
    loading: transLoading,
  } = useRequest(RiskManageService.transRisk, {
    defaultValue: null,
    onSuccess() {
      emits('update');
      handleChangeMethod('closeOrder');
      messageSuccess(t('人工转单成功'));
    },
  });

  const handleChangeMethod = (val: string | number | boolean) => {
    let params = {};
    switch (val as string) {
    case 'closeOrder':
      params = {
        description: '',
      };
      break;
    case 'transfer':
      params = {
        description: '',
        new_operators: [],
      };
      break;
    case 'ProcessPackage':
      params = {
        pa_id: '',
        pa_params: {},
        auto_close_risk: false,
      };
      paramsDetailData.value = {};
      formData.value.pa_params = {};
      break;
    }
    formData.value = {
      method: val,
      ...params,
      risk_id: props.riskId,
    };
  };
  const handleSubmit = () => {
    formRef.value.validate().then(() => {
      switch (formData.value.method) {
      case 'closeOrder':
        close(formData.value);
        break;
      case 'transfer':
        transRisk({
          ...formData.value,
        });
        break;
      case 'ProcessPackage':
        autoProcess(formData.value);
        break;
      }
    });
  };
  const handleCancel = () => {
    router.push({
      name: route.name === 'riskManageDetail'
        ? 'riskManageList'
        : 'handleManageList',
    });
  };

  watch(
    () => formData.value, (val) => {
      Object.keys(paramsDetailData.value).forEach((obj) => {
        if (paramsDetailData.value[obj]?.hide_condition) {
          const hideCondition = paramsDetailData.value[obj]?.hide_condition;
          // 添加安全检查，确保hideCondition存在且是数组
          if (hideCondition && Array.isArray(hideCondition)) {
            hideCondition.forEach((item: any) => {
              // 根据操作符进行条件判断
              const oldIsHide = paramsDetailData.value[obj].is_hide;
              switch (item.operator) {
              case '=':
                paramsDetailData.value[obj].is_hide = (
                  item.value.toString() === val.pa_params[item.constant_key].value.toString()
                );
                break;
              default:
                paramsDetailData.value[obj].is_hide = false;
                break;
              }
              // 当字段从显示变为隐藏时，重置对应的参数值
              if (!oldIsHide && paramsDetailData.value[obj].is_hide) {
                formData.value.pa_params[paramsDetailData.value[obj].key].value = '';
                formData.value.pa_params[paramsDetailData.value[obj].key].field = '';
              }
            });
          }
        }
      });
    },
    { deep: true },
  );
</script>
<style scoped>
.risk-await-deal-wrap {
  padding: 10px 16px;
  font-size: 12px;
  background: #fff;
  border: 1px solid #eaebf0;
  border-radius: 6px;
  box-shadow: 0 2px 6px 0 #0000000a;
}

.val-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%
}

.line-down {
  font-size: 12px;
  cursor: pointer;
}

.label-text {
  cursor: pointer;
}

:deep(.bk-form-item.is-required .bk-form-label::after) {
  display: none;
}

.label-name::after {
  top: 0;
  width: 14px;
  margin-left: 5px;
  color: #ea3636;
  text-align: center;
  content: '*';
}

.underline {
  border-bottom: 1px dashed #c4c6cc;
}
</style>
