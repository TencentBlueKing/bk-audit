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
  <div
    class="risk-await-deal-wrap"
    :class="{ 'is-editor-boosted': isDockEditorBoosted }">
    <audit-form
      ref="formRef"
      form-type="vertical"
      :model="formData"
      :rules="rules">
      <bk-form-item
        class="risk-await-deal-method"
        :label="t('处理方法')"
        required>
        <bk-radio-group
          class="risk-await-deal-method__group"
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
            class="await-deal-rich-editor"
            :default="formData.description"
            fullscreen-scope="parent"
            :max-len="1000"
            @expand-change="handleEditorExpandChange" />
        </bk-form-item>
      </template>
      <!-- 转单 -->
      <template v-else-if="formData.method === 'transfer'">
        <bk-form-item
          :label="t('转单人员')"
          property="new_operators"
          required>
          <audit-user-selector-tenant
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
            class="await-deal-rich-editor"
            :default="formData.description"
            fullscreen-scope="parent"
            :max-len="1000"
            @expand-change="handleEditorExpandChange" />
        </bk-form-item>
      </template>

      <!-- 标记误报 -->
      <template v-else-if="formData.method === 'misreport'">
        <bk-alert
          class="misreport-alert"
          theme="warning"
          :title="t('标记误报后，风险单会自动关闭，请谨慎确认是否为误报？')" />
        <bk-form-item
          class="is-required"
          :label="t('误报说明')"
          property="misreport_description"
          required>
          <bk-input
            v-model.trim="formData.misreport_description"
            :maxlength="100"
            :placeholder="t('请输入')"
            show-word-limit
            type="textarea" />
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
            class="is-required pa-params-form-item"
            :label="t('套餐参数')"
            property="pa_params">
            <div class="pa-params-grid">
              <template
                v-for="(val, index) in Object.values(sortByIndex (paramsDetailData))"
                :key="`${val.key}-${index}`">
                <bk-form-item
                  v-if="val.show_type === 'show' && !val.is_hide"
                  class="pa-params-field"
                  :label="val.name"
                  :property="`pa_params.${val.key}`"
                  required
                  :rules="[
                    { message: t('不能为空'),
                      validator: (value: any) => handlePaValidate(value) },
                  ]">
                  <application-parameter
                    v-model="formData.pa_params[val.key]"
                    clearable
                    :config="val"
                    :detail-data="detailData"
                    :event-data-list="eventDataList"
                    :risk-field-list="riskFieldList"
                    use-field-insert />
                  <template #error="message">
                    <div>{{ val.name }}{{ message }}</div>
                  </template>
                  <template #label>
                    <span
                      v-bk-tooltips="{
                        content: t(val.desc),
                        disabled: val.desc === '',
                      }"
                      :class="val.desc === '' ? 'label-name' : 'label-name underline'">{{ val.name }}</span>
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
          action-id="process_risk"
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
  import DOMPurify from 'dompurify';
  import {
    computed,
    inject,
    ref,
    watch,
    type Ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    onBeforeRouteLeave,
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
  const dockEditorExpand = inject<(expanded: boolean) => void>('dockEditorExpand', () => {});
  const dockBoostState = inject<{
    isEditorBoosted: Ref<boolean>;
    panelHeight: Ref<number>;
  } | null>('dockBoostState', null);
  const dockCollapse = inject<(() => void) | null>('dockCollapse', null);
  const isDockEditorBoosted = computed(() => dockBoostState?.isEditorBoosted.value ?? false);
  const handleEditorExpandChange = (expanded: boolean) => {
    dockEditorExpand(expanded);
  };
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
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
    misreport_description: [{
      validator: (value: string) => !!value,
      trigger: 'blur',
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
  const radioGroup = computed(() => {
    const options = [
      { id: 'closeOrder', name: '人工关单' },
      { id: 'transfer', name: '转单' },
      { id: 'ProcessPackage', name: '处理套餐' },
    ];
    if (props.detailData.risk_label !== 'misreport') {
      options.push({ id: 'misreport', name: '标记误报' });
    }
    return options;
  });

  const formData = ref<Record<string, any>>({
    method: 'closeOrder',
    risk_id: props.riskId,
  });
  const formRef = ref();
  const loading = computed(() => transLoading.value || autoProcessLoading.value
    || closeLoading.value || misreportLoading.value);
  const filterProcessApplicationList = computed(() => processApplicationList.value
    .filter(item => item.is_enabled));

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

  const handlePaValidate = (value: { field: string; value: string }) => {
    const isEmpty = (v: any) => v === undefined
      || v === null
      || v === ''
      || (Array.isArray(v) && v.length === 0);
    if (!value || typeof value !== 'object') return false;
    const { field, value: val } = value;
    const isFieldEmpty = isEmpty(field);
    const isValueEmpty = isEmpty(val);
    // field 和 value 同时为空，才算不通过
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
    defaultParams: {
      scene_id: props.detailData.scene_id,
    },
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

  const resetForm = () => {
    paramsDetailData.value = {};
    handleChangeMethod('closeOrder');
    formRef.value?.clearValidate?.();
  };

  const handleSubmitSuccess = (message: string) => {
    handleEditorExpandChange(false);
    resetForm();
    dockCollapse?.();
    emits('update');
    messageSuccess(message);
  };

  // 标记误报
  const {
    run: updateRiskLabel,
    loading: misreportLoading,
  } = useRequest(RiskManageService.updateRiskLabel, {
    defaultValue: null,
    onSuccess() {
      handleSubmitSuccess(t('标记误报成功'));
    },
  });
  // 人工执行处理套餐
  const {
    run: autoProcess,
    loading: autoProcessLoading,
  } = useRequest(RiskManageService.autoProcess, {
    defaultValue: null,
    onSuccess() {
      handleSubmitSuccess(t('人工处理提交处理套餐成功'));
    },
  });
  // 人工关单
  const {
    run: close,
    loading: closeLoading,
  } = useRequest(RiskManageService.close, {
    defaultValue: null,
    onSuccess() {
      handleSubmitSuccess(t('人工关单成功'));
    },
  });
  // 人工转单
  const {
    run: transRisk,
    loading: transLoading,
  } = useRequest(RiskManageService.transRisk, {
    defaultValue: null,
    onSuccess() {
      handleSubmitSuccess(t('人工转单成功'));
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
    case 'misreport':
      params = {
        misreport_description: '',
      };
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
      case 'misreport':
        updateRiskLabel({
          risk_id: props.riskId,
          risk_label: 'misreport',
          description: formData.value.misreport_description,
        });
        break;
      }
    });
  };

  // 判断富文本内容是否为实质性输入（排除编辑器产生的空内容HTML标签）
  const isRichTextNotEmpty = (html: string) => {
    if (!html) return false;
    // 使用 DOMPurify 安全地去除所有HTML标签，只保留纯文本内容
    const text = DOMPurify.sanitize(html, { ALLOWED_TAGS: [] }).trim();
    return text.length > 0;
  };

  // 判断当前表单是否有实质性用户输入
  const hasSubstantialInput = () => {
    const { method, description, new_operators: newOperators, pa_id: paId,
            misreport_description: misreportDescription } = formData.value;
    switch (method) {
    case 'closeOrder':
      return isRichTextNotEmpty(description);
    case 'transfer':
      return isRichTextNotEmpty(description) || (newOperators && newOperators.length > 0);
    case 'ProcessPackage':
      return !!paId;
    case 'misreport':
      return !!misreportDescription;
    default:
      return false;
    }
  };

  const handleCancel = () => {
    if (!hasSubstantialInput()) {
      window.changeConfirm = false;
    }
    handleEditorExpandChange(false);
    resetForm();
    dockCollapse?.();
  };

  // 路由离开前判断：如果没有实质性输入，则不弹确认弹窗
  onBeforeRouteLeave(() => {
    if (!hasSubstantialInput()) {
      window.changeConfirm = false;
    }
  });

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
  width: 100%;
  max-width: 100%;
  padding: 16px;
  margin: 0;
  font-size: 12px;
  background: #f5f7fa;
  border: 1px solid #eaebf0;
  border-radius: 4px;
  box-sizing: border-box;
}

.risk-await-deal-wrap :deep(.bk-form),
.risk-await-deal-wrap :deep(.bk-form-item),
.risk-await-deal-wrap :deep(.bk-form-content) {
  width: 100%;
  max-width: 100%;
}

.risk-await-deal-wrap :deep(.bk-form-item) {
  margin-bottom: 16px;
}

.risk-await-deal-wrap :deep(.bk-form-item:last-child) {
  margin-bottom: 0;
}

.risk-await-deal-wrap :deep(.bk-form-label) {
  font-size: 12px;
  line-height: 20px;
  color: #313238;
}

.risk-await-deal-method__group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}

.risk-await-deal-wrap :deep(.bk-select),
.risk-await-deal-wrap :deep(.bk-input) {
  width: 100%;
}

:deep(.await-deal-rich-editor),
:deep(.await-deal-rich-editor .editor-wrap),
:deep(.await-deal-rich-editor .quill-editor) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.misreport-alert {
  margin-bottom: 16px;
}

.pa-params-form-item {
  :deep(.bk-form-content) {
    max-width: 100%;
  }
}

.pa-params-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px 24px;
  padding: 16px 12px;
  background: #f5f7fa;
  border: 1px solid #dcdee5;
  border-radius: 2px;
}

.pa-params-field {
  width: 100%;
  margin-bottom: 0 !important;

  :deep(.bk-form-item) {
    display: block;
  }

  :deep(.bk-form-label) {
    width: 100% !important;
    padding-bottom: 4px;
    text-align: left;
  }

  :deep(.bk-form-content) {
    margin-left: 0 !important;
  }
}

.risk-await-deal-wrap.is-editor-boosted {
  :deep(.await-deal-rich-editor.expanded-mode) {
    display: flex;
    flex-direction: column;
  }

  :deep(.bk-form-item:has(.await-deal-rich-editor.expanded-mode)) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    margin-bottom: 12px;

    .bk-form-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }
  }
}

:deep(.await-deal-rich-editor .ql-container) {
  min-height: 180px;
  transition: min-height .2s ease, height .2s ease;
}

:deep(.await-deal-rich-editor.expanded-mode) {
  height: var(--editor-expanded-height, 360px);
}

:deep(.await-deal-rich-editor.expanded-mode .ql-container) {
  height: auto !important;
  min-height: 0 !important;
  flex: 1;
}

:deep(.await-deal-rich-editor.expanded-mode .ql-editor) {
  min-height: 0 !important;
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
