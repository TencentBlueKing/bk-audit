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
    class="risk-await-deal-wrap bk-theme-form--compact"
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
            :max-len="2000"
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
            allow-create
            class="transfer-user-selector"
            :placeholder="t('请输入用户名，或通过输入$使用变量')"
            :user-group="memberVariables"
            :user-group-name="t('可使用变量')"
            @change="handleTransferOperatorsChange" />
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
            :max-len="2000"
            @expand-change="handleEditorExpandChange" />
        </bk-form-item>
      </template>

      <!-- 标记误报 -->
      <template v-else-if="formData.method === 'misreport'">
        <bk-alert
          class="misreport-alert"
          theme="warning"
          :title="misreportAlertTitle" />
        <bk-form-item
          class="is-required"
          :label="t('误报说明')"
          property="misreport_description"
          required>
          <rich-editor
            ref="misreportRichEditor"
            v-model:content="formData.misreport_description"
            class="await-deal-rich-editor"
            :default="formData.misreport_description"
            fullscreen-scope="parent"
            :max-len="2000"
            @expand-change="handleEditorExpandChange" />
        </bk-form-item>
        <bk-checkbox
          v-model="withWhitelist"
          class="whitelist-together">
          {{ t(roleText.text.value.together) }}
        </bk-checkbox>
        <risk-whitelist-form
          v-if="withWhitelist"
          ref="whitelistFormRef"
          embedded
          :initial-scope="initialScope"
          show-apply-hint />
      </template>

      <!-- 加入白名单 / 申请加白 -->
      <template v-else-if="formData.method === 'whitelist'">
        <risk-whitelist-form
          ref="whitelistFormRef"
          embedded
          :initial-scope="initialScope"
          show-apply-hint />
      </template>

      <!-- 处理套餐 -->
      <template v-else-if="formData.method === 'ProcessPackage'">
        <bk-form-item
          class="is-required process-package-select-item"
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
            v-if="hasUserInputParams"
            class="pa-params-form-item"
            :label="t('套餐参数')"
            property="pa_params">
            <div class="pa-params-grid">
              <template
                v-for="(val, index) in Object.values(sortByIndex (paramsDetailData))"
                :key="`${val.key}-${index}`">
                <bk-form-item
                  v-if="isUserInput(val) && !val.is_hide"
                  class="pa-params-field"
                  :label="val.name"
                  :property="`pa_params.${val.key}`">
                  <application-parameter
                    v-model="formData.pa_params[val.key]"
                    clearable
                    :config="val"
                    :detail-data="detailData"
                    :event-data-list="eventDataList"
                    :risk-field-list="riskFieldList"
                    use-field-insert
                    :user-group="memberVariables"
                    :user-group-name="t('可使用变量')" />
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
          class="auto-close-risk-form-item"
          label="">
          <bk-checkbox v-model="formData.auto_close_risk">
            <span style="font-size: 12px;">{{ t('套餐执行成功后自动关单') }}</span>
          </bk-checkbox>
        </bk-form-item>
      </template>
      <bk-form-item
        class="submit-actions-form-item"
        label="">
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
    <whitelist-confirm-dialog ref="confirmRef" />
  </div>
</template>

<script setup lang='ts'>
  import DOMPurify from 'dompurify';
  import {
    computed,
    inject,
    nextTick,
    ref,
    watch,
    type Ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    onBeforeRouteLeave,
  } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import ProcessApplicationManageService from '@service/process-application-manage';
  import RiskManageService from '@service/risk-manage';
  import RiskWhitelistService from '@service/risk-whitelist';
  import SoapManageService from '@service/soap-manage';

  import type RiskManageModel from '@model/risk/risk';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useWhitelistRoleText from '@hooks/use-whitelist-role-text';

  import ApplicationParameter from '@components/application-parameter/index.vue';
  import RichEditor from '@components/editor/index.vue';
  import RiskWhitelistForm from '@components/risk-whitelist-form/index.vue';
  import WhitelistConfirmDialog from '@components/whitelist-confirm-dialog/index.vue';

  import { buildScopeFromRisk } from '@views/risk-manage/whitelist';

  import {
    buildSubmitPaParams,
    isUserInput,
    syncPaParamVisibility,
  } from '@/utils/assist/pa-param-submit';

  interface Props {
    riskId: string,
    detailData: RiskManageModel,
    userInfo: {
      username: string,
    },
    eventDataList: Record<string, any>[],
    requestedMethod?: string,
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
  const { messageSuccess, messageError } = useMessage();
  const roleText = useWhitelistRoleText();
  const whitelistFormRef = ref<InstanceType<typeof RiskWhitelistForm>>();
  const confirmRef = ref<InstanceType<typeof WhitelistConfirmDialog>>();
  const withWhitelist = ref(false);
  const initialScope = computed(() => buildScopeFromRisk({
    strategy_id: props.detailData.strategy_id,
    strategy_name: (props.detailData as RiskManageModel & { strategy_name?: string }).strategy_name,
    raw_event_id: props.detailData.raw_event_id,
  }));
  const misreportAlertTitle = computed(() => (
    `${t('标记误报后，风险单将自动关闭。若需避免后续同类风险再次命中，')}${t(roleText.text.value.misreportAlertTail)}`
  ));

  const { data: memberVariableSource } = useRequest(MetaManageService.fetchVariableList, {
    defaultValue: [],
  });

  const memberVariables = computed(() => {
    const list = Array.isArray(memberVariableSource.value) ? memberVariableSource.value : [];
    return list.map((item: { value?: string; label?: string }) => ({
      id: String(item.value || ''),
      name: `${item.value}(${item.label})`,
    })).filter(item => item.id);
  });

  // 判断富文本内容是否为实质性输入（排除编辑器产生的空内容HTML标签）
  const isRichTextNotEmpty = (html: string) => {
    if (!html) return false;
    const text = DOMPurify.sanitize(html, { ALLOWED_TAGS: [] }).trim();
    return text.length > 0;
  };

  const hasTransferOperators = (value: string | string[] | undefined) => {
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return !!value;
  };

  const clearFieldValidateIfValid = (field: string, isValid: boolean) => {
    if (!isValid) return;
    nextTick(() => {
      formRef.value?.clearValidate?.(field);
    });
  };

  const rules = {
    new_operators: [{
      validator: (value: string | string[]) => hasTransferOperators(value),
      trigger: 'change',
      message: t('转单人不能为空'),
    }],
    description: [{
      validator: (value: string) => isRichTextNotEmpty(value),
      trigger: 'change',
      message: t('说明不能为空'),
    }],
    misreport_description: [{
      validator: (value: string) => isRichTextNotEmpty(value),
      trigger: 'change',
      message: t('说明不能为空'),
    }],
    pa_id: [{
      validator: (value: string) => !!value,
      trigger: 'change',
      message: t('处理套餐不能为空'),
    }],
  };
  const radioGroup = computed(() => {
    const options = [
      { id: 'closeOrder', name: '人工关单' },
      { id: 'transfer', name: '转单' },
      { id: 'ProcessPackage', name: '处理套餐' },
    ];
    if (props.detailData.status === 'closed') {
      return [{ id: 'misreport', name: '标记误报' }];
    }
    if (props.detailData.risk_label !== 'misreport') {
      options.push({ id: 'misreport', name: '标记误报' });
    }
    options.push({ id: 'whitelist', name: roleText.text.value.method });
    return options;
  });

  const defaultHandleMethod = () => (
    props.detailData.status === 'closed' ? 'misreport' : 'closeOrder'
  );

  const formData = ref<Record<string, any>>({
    method: defaultHandleMethod(),
    risk_id: props.riskId,
  });
  const formRef = ref();
  const loading = computed(() => transLoading.value || autoProcessLoading.value
    || closeLoading.value || misreportLoading.value || detailLoading.value || applyLoading.value);
  const filterProcessApplicationList = computed(() => processApplicationList.value
    .filter(item => item.is_enabled));

  const handlePaIdChange = (id: string) => {
    if (id) {
      paramsDetailData.value = {};
      formData.value.pa_params = {};
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

  const handleTransferOperatorsChange = () => {
    clearFieldValidateIfValid(
      'new_operators',
      hasTransferOperators(formData.value.new_operators),
    );
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
  const hasUserInputParams = computed(() => Object.values(paramsDetailData.value).some(isUserInput));
  const {
    run: fetchDetail,
    loading: detailLoading,
  } = useRequest(SoapManageService.fetchDetail, {
    defaultValue: {},
    onSuccess(data) {
      if (!formData.value.pa_id) {
        return;
      }
      // 给对象中的每一项添加 type: 'self',
      Object.keys(data).forEach((key) => {
        // eslint-disable-next-line no-param-reassign
        data[key].type = 'self';
        // eslint-disable-next-line no-param-reassign
        data[key].is_hide = false;
      });
      paramsDetailData.value = data;
      formData.value.pa_params = {};
      syncPaParamVisibility(formData.value.pa_params, Object.values(data));
    },
  });

  const resetForm = () => {
    paramsDetailData.value = {};
    handleChangeMethod(defaultHandleMethod());
    formRef.value?.clearValidate?.();
  };

  const handleSubmitSuccess = (message: string, shouldCollapse = false) => {
    handleEditorExpandChange(false);
    resetForm();
    if (shouldCollapse) {
      dockCollapse?.();
    }
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
  const {
    run: applyWhitelist,
    loading: applyLoading,
  } = useRequest(RiskWhitelistService.applyFromRisk, {
    defaultValue: null,
    onSuccess() {
      const withMisreport = formData.value.method === 'misreport';
      handleSubmitSuccess(withMisreport
        ? t(roleText.text.value.misreportSuccess)
        : t(roleText.text.value.applySuccess));
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
      withWhitelist.value = false;
      break;
    case 'whitelist':
      params = {};
      withWhitelist.value = false;
      break;
    }
    formData.value = {
      method: val,
      ...params,
      risk_id: props.riskId,
    };
  };

  const openWhitelistConfirm = async () => {
    if (!whitelistFormRef.value?.validate()) {
      messageError(t('请完整填写加白信息'));
      return;
    }
    const payload = whitelistFormRef.value.getPayload();
    const confirmed = await confirmRef.value?.open({
      scope: payload.match_scope,
      whitelistType: payload.whitelist_type,
      validityMode: payload.validity_mode || 'permanent',
      customDays: payload.custom_days,
      source: 'risk',
    });
    if (!confirmed) return;
    applyWhitelist({
      risk_id: props.riskId,
      ...payload,
      with_misreport: formData.value.method === 'misreport',
      misreport_description: formData.value.misreport_description || '',
      source: 'risk',
    });
  };

  const handleSubmit = () => {
    if (detailLoading.value) {
      return;
    }
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
        autoProcess({
          ...formData.value,
          pa_params: buildSubmitPaParams(formData.value.pa_params, Object.values(paramsDetailData.value)),
        });
        break;
      case 'misreport':
        if (withWhitelist.value) {
          openWhitelistConfirm();
          return;
        }
        updateRiskLabel({
          risk_id: props.riskId,
          risk_label: 'misreport',
          description: formData.value.misreport_description || '',
        });
        break;
      case 'whitelist':
        openWhitelistConfirm();
        break;
      }
    });
  };

  // 判断当前表单是否有实质性用户输入
  const hasSubstantialInput = () => {
    const { method, description, new_operators: newOperators, pa_id: paId,
            misreport_description: misreportDescription } = formData.value;
    switch (method) {
    case 'closeOrder':
      return isRichTextNotEmpty(description);
    case 'transfer':
      return isRichTextNotEmpty(description) || hasTransferOperators(newOperators);
    case 'ProcessPackage':
      return !!paId;
    case 'misreport':
      return isRichTextNotEmpty(misreportDescription)
        || (withWhitelist.value && (whitelistFormRef.value?.isDirty() ?? false));
    case 'whitelist':
      return whitelistFormRef.value?.isDirty() ?? false;
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
    () => formData.value.new_operators,
    (operators) => {
      clearFieldValidateIfValid('new_operators', hasTransferOperators(operators));
    },
    { deep: true },
  );

  watch(
    () => formData.value.description,
    (description) => {
      clearFieldValidateIfValid('description', isRichTextNotEmpty(description));
    },
  );

  watch(
    () => formData.value.misreport_description,
    (description) => {
      clearFieldValidateIfValid('misreport_description', isRichTextNotEmpty(description));
    },
  );

  watch(
    () => props.requestedMethod,
    (method) => {
      if (!method) return;
      const nextMethod = method.startsWith('misreport') ? 'misreport' : method;
      if (radioGroup.value.some(item => item.id === nextMethod)) {
        handleChangeMethod(nextMethod);
      }
    },
    { immediate: true },
  );

  watch(
    () => formData.value.pa_params,
    paParams => syncPaParamVisibility(paParams, Object.values(paramsDetailData.value)),
    { deep: true },
  );
</script>
<style scoped>
.risk-await-deal-wrap {
  width: 100%;
  max-width: 100%;
  padding: var(--bk-theme-space-16);
  margin: 0;
  font-size: 12px;
  background: var(--bk-theme-surface-subtle);
  border: 1px solid var(--bk-theme-border-weak);
  border-radius: var(--bk-theme-tag-radius);
  box-sizing: border-box;
}

.risk-await-deal-wrap :deep(.bk-form),
.risk-await-deal-wrap :deep(.bk-form-item),
.risk-await-deal-wrap :deep(.bk-form-content) {
  width: 100%;
  max-width: 100%;
}

.risk-await-deal-wrap :deep(.bk-form-item) {
}

.risk-await-deal-wrap :deep(.bk-form-item:last-child) {
}

.risk-await-deal-wrap :deep(.bk-form-error) {
  position: static;
  display: block;
  padding-top: var(--bk-theme-space-4);
  line-height: 18px;
}

.risk-await-deal-wrap :deep(.bk-form-label) {
  font-size: 12px;
  line-height: 20px;
  color: var(--bk-theme-text-strong);
}

.risk-await-deal-method__group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--bk-theme-space-8) var(--bk-theme-space-24);
}

.risk-await-deal-method__group :deep(.bk-radio) {
  font-size: 12px;
  font-weight: 400;
  line-height: 20px;
  color: var(--bk-theme-text-default);
}

.risk-await-deal-method__group :deep(.bk-radio .bk-radio-label) {
  font-size: 12px;
  font-weight: 400;
  line-height: 20px;
  color: var(--bk-theme-text-default);
}

.risk-await-deal-wrap :deep(.bk-select),
.risk-await-deal-wrap :deep(.bk-input),
.risk-await-deal-wrap :deep(.transfer-user-selector),
.risk-await-deal-wrap :deep(.pa-params-grid .bk-user-selector) {
  width: 100%;
}

.risk-await-deal-wrap :deep(.bk-user-selector) {
  min-width: 0;

  .custom-tag {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

:deep(.await-deal-rich-editor),
:deep(.await-deal-rich-editor .editor-wrap),
:deep(.await-deal-rich-editor .quill-editor) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.misreport-alert,
.whitelist-apply-hint {
  margin-bottom: var(--bk-theme-space-16);
}

.whitelist-together {
  margin-bottom: var(--bk-theme-space-16);
  font-size: var(--bk-theme-font-size-sm);
  color: var(--bk-theme-text-default);
}

.risk-await-deal-wrap :deep(.risk-whitelist-form.is-embedded) {
  margin-bottom: var(--bk-theme-space-24);
}

.pa-params-form-item {
  margin-top: var(--bk-theme-space-24) !important;
  margin-bottom: 0 !important;

  :deep(.bk-form-content) {
    max-width: 100%;
  }
}

.process-package-select-item {
  margin-bottom: 0 !important;
}

.auto-close-risk-form-item {
  margin-top: var(--bk-theme-space-24) !important;
  margin-bottom: var(--bk-theme-space-24) !important;
}

.submit-actions-form-item {
  margin-top: var(--bk-theme-space-8) !important;
  margin-bottom: 0 !important;
}

.submit-actions-form-item :deep(.bk-form-label) {
  display: none;
}

.pa-params-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--bk-theme-space-16);
  padding: var(--bk-theme-space-16) var(--bk-theme-space-12);
  background: var(--bk-theme-surface-muted);
  border: 1px solid var(--bk-theme-border-default);
  border-radius: var(--bk-theme-tag-radius);

  /* 套餐参数组件统一高度 32px */
  :deep(.bk-select),
  :deep(.bk-input:not(textarea, .bk-textarea)),
  :deep(.bk-date-picker),
  :deep(.bk-date-picker-rel),
  :deep(.bk-date-picker-editor),
  :deep(.pa-user-selector.bk-user-selector),
  :deep(.pa-user-selector .user-selector-input) {
    height: 32px;
    max-height: 32px;
    min-height: 32px;
    box-sizing: border-box;
  }

  :deep(.field-insert-wrapper:not(.is-textarea).has-suffix) {
    height: 32px;
    align-items: center;
  }

  :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__main),
  :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__control),
  :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__suffix-host),
  :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__suffix) {
    height: 32px;
    max-height: 32px;
    min-height: 32px;
    box-sizing: border-box;
  }
}

.pa-params-field {
  width: 100%;
  margin-bottom: 0 !important;

  :deep(.bk-form-item) {
    display: block;
  }

  :deep(.bk-form-label) {
    width: 100% !important;
    padding-bottom: 0;
    text-align: left;
  }

  :deep(.bk-form-content) {
    max-width: 100%;
    min-width: 0;
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

.risk-await-deal-wrap :deep(.risk-whitelist-form .bk-form-item.is-required .bk-form-label::after) {
  display: inline-block;
  margin-left: var(--bk-theme-space-2);
  color: var(--bk-theme-color-danger-2);
  content: '*';
}

.label-name::after {
  top: 0;
  width: 14px;
  margin-left: var(--bk-theme-space-4);
  color: var(--bk-theme-color-danger-2);
  text-align: center;
  content: '*';
}

.underline {
  border-bottom: 1px dashed var(--bk-theme-border-strong);
}
</style>
