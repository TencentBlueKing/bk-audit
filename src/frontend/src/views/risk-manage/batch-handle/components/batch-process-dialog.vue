<template>
  <bk-dialog
    v-model:is-show="isShow"
    :esc-close="false"
    :quick-close="false"
    :title="t('批量处理')"
    :width="dialogWidth"
    @closed="resetForm">
    <div
      class="risk-await-deal-wrap"
      data-testid="batch-process-dialog">
      <p class="batch-process-hint">
        {{ t('已选择') }} {{ count }} {{ t('条风险，提交后将按相同处理方法统一执行。') }}
      </p>
      <audit-form
        ref="formRef"
        form-type="vertical"
        :model="formData"
        :rules="rules">
        <bk-form-item
          class="risk-await-deal-method"
          :label="t('处理方法')"
          property="method"
          required>
          <bk-radio-group
            v-model="formData.method"
            class="risk-await-deal-method__group">
            <span
              v-for="action in actionOptions"
              :key="action.method"
              v-bk-tooltips="{ content: t(action.reason), disabled: action.enabled || !action.reason }">
              <bk-radio
                :disabled="!action.enabled"
                :label="action.method">
                {{ action.label }}
              </bk-radio>
            </span>
          </bk-radio-group>
        </bk-form-item>

        <template v-if="formData.method === 'closeOrder'">
          <bk-form-item
            :label="t('处理说明')"
            property="description">
            <rich-editor
              :key="editorKey"
              v-model:content="formData.description"
              class="await-deal-rich-editor"
              :default="formData.description"
              :event-fields="eventFields"
              :max-len="1000"
              :risk-fields="riskFields"
              support-variable />
          </bk-form-item>
        </template>

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
              :user-group-name="t('可使用变量')" />
          </bk-form-item>
          <bk-form-item
            :label="t('处理说明')"
            property="description">
            <rich-editor
              :key="`${editorKey}-transfer`"
              v-model:content="formData.description"
              class="await-deal-rich-editor"
              :default="formData.description"
              :event-fields="eventFields"
              :max-len="1000"
              :risk-fields="riskFields"
              support-variable />
          </bk-form-item>
        </template>

        <template v-else-if="formData.method === 'ProcessPackage'">
          <bk-form-item
            class="is-required process-package-select-item"
            :label="t('处理套餐')"
            property="pa_id">
            <bk-select
              v-model="formData.pa_id"
              filterable
              :loading="applicationLoading || packageMerging"
              :placeholder="t('请选择')"
              @change="handlePaIdChange">
              <bk-option
                v-for="item in enabledApplications"
                :key="item.id"
                :label="item.name"
                :value="item.id" />
            </bk-select>
          </bk-form-item>
          <bk-loading :loading="detailLoading">
            <bk-form-item
              v-if="Object.keys(paramsDetailData).length"
              class="is-required pa-params-form-item"
              :label="t('套餐参数')"
              property="pa_params">
              <div class="pa-params-grid">
                <template
                  v-for="(val, index) in sortedParams"
                  :key="`${val.key}-${index}`">
                  <bk-form-item
                    v-if="val.show_type === 'show' && !val.is_hide"
                    class="pa-params-field"
                    :label="val.name"
                    :property="`pa_params.${val.key}`"
                    required
                    :rules="[{
                      message: t('不能为空'),
                      validator: (value: PackageParamValue) => isPackageParamFilled(value),
                    }]">
                    <application-parameter
                      v-model="formData.pa_params[val.key]"
                      clearable
                      :config="val"
                      :detail-data="{}"
                      :event-data-list="eventDataList"
                      insert-by-field-name
                      :risk-field-list="riskFields"
                      use-field-insert
                      :user-group="memberVariables"
                      :user-group-name="t('可使用变量')" />
                    <template #label>
                      <span
                        v-bk-tooltips="{ content: t(val.desc), disabled: !val.desc }"
                        :class="val.desc ? 'label-name underline' : 'label-name'">
                        {{ val.name }}
                      </span>
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

        <template v-else-if="formData.method === 'misreport'">
          <bk-alert
            class="misreport-alert"
            theme="warning"
            :title="t('标记误报后，风险单会自动关闭，请谨慎确认是否为误报？')" />
          <bk-form-item
            :label="t('误报说明')"
            property="misreport_description">
            <rich-editor
              :key="`${editorKey}-misreport`"
              v-model:content="formData.misreport_description"
              class="await-deal-rich-editor"
              :default="formData.misreport_description"
              :event-fields="eventFields"
              :max-len="1000"
              :risk-fields="riskFields"
              support-variable />
          </bk-form-item>
        </template>
      </audit-form>
      <div
        v-if="failures.length"
        class="batch-process-failures"
        data-testid="batch-handle-failures">
        <div>{{ t('部分风险处理失败') }}</div>
        <div
          v-for="item in failures"
          :key="item.risk_id">
          {{ item.risk_id }}：{{ item.reason }}
        </div>
      </div>
    </div>
    <template #footer>
      <bk-button
        data-testid="batch-process-submit"
        :loading="isSubmitting"
        theme="primary"
        @click="handleSubmit">
        {{ t('确定') }}
      </bk-button>
      <bk-button
        class="ml8"
        :disabled="isSubmitting"
        @click="isShow = false">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import DOMPurify from 'dompurify';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import ProcessApplicationManageService from '@service/process-application-manage';
  import SoapManageService from '@service/soap-manage';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import ApplicationParameter from '@components/application-parameter/index.vue';
  import RichEditor from '@components/editor/index.vue';

  import { submitBatchProcess, type PackageParamValue } from '../adapter';
  import { defaultBatchAction, type BatchActionId, type BatchAvailability } from '../evaluate';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  interface FieldItem {
    id: string;
    name: string;
  }

  interface PackageParam {
    custom_type?: string;
    desc: string;
    index: number;
    key: string;
    name: string;
    show_type: string;
    type?: string;
    is_hide?: boolean;
    hide_condition?: Array<{ operator: string; value: string | number; constant_key: string }>;
  }

  interface Props {
    count: number;
    riskIds: string[];
    availability: BatchAvailability;
    scope?: 'scene' | 'all';
    riskFields?: FieldItem[];
    eventFields?: FieldItem[];
  }

  const props = withDefaults(defineProps<Props>(), {
    scope: 'scene',
    riskFields: () => [],
    eventFields: () => [],
  });

  const emit = defineEmits<{(e: 'success'): void }>();

  const METHOD_BY_ACTION: Record<BatchActionId, string> = {
    close: 'closeOrder',
    transfer: 'transfer',
    package: 'ProcessPackage',
    misreport: 'misreport',
  };

  const ACTION_BY_METHOD: Record<string, BatchActionId> = {
    closeOrder: 'close',
    transfer: 'transfer',
    ProcessPackage: 'package',
    misreport: 'misreport',
  };

  const { t } = useI18n();
  const { messageSuccess, messageError } = useMessage();
  const isShow = ref(false);
  const isSubmitting = ref(false);
  const packageMerging = ref(false);
  const editorKey = ref(0);
  const formRef = ref();
  const failures = ref<Array<{ risk_id: string; reason: string }>>([]);
  const paramsDetailData = ref<Record<string, PackageParam>>({});

  const createForm = () => {
    const action = defaultBatchAction(props.availability.actions);
    return {
      method: action ? METHOD_BY_ACTION[action] : '',
      description: '',
      misreport_description: '',
      new_operators: [] as string[],
      pa_id: '',
      pa_params: {} as Record<string, PackageParamValue>,
      auto_close_risk: false,
    };
  };

  const formData = ref(createForm());

  const actionLabels: Record<BatchActionId, string> = {
    close: '人工关单',
    transfer: '转单',
    package: '处理套餐',
    misreport: '标记误报',
  };

  const actionOptions = computed(() => props.availability.actions.map(action => ({
    ...action,
    method: METHOD_BY_ACTION[action.id],
    label: t(actionLabels[action.id]),
  })));

  const dialogWidth = computed(() => (formData.value.method === 'ProcessPackage' ? 1080 : 960));

  const eventDataList = computed(() => props.eventFields.map(item => ({
    id: item.id,
    lable: item.name,
    value: '',
  })));

  const sortedParams = computed(() => Object.values(paramsDetailData.value)
    .sort((prev, next) => prev.index - next.index));

  const hasTransferOperators = (value: string | string[] | undefined) => (
    Array.isArray(value) ? value.length > 0 : Boolean(value)
  );

  const isPackageParamFilled = (value: PackageParamValue) => {
    if (!value) {
      return false;
    }
    const fieldEmpty = value.field === undefined || value.field === null || value.field === '';
    const raw = value.value;
    const valueEmpty = raw === undefined
      || raw === null
      || raw === ''
      || (Array.isArray(raw) && raw.length === 0);
    return !(fieldEmpty && valueEmpty);
  };

  const rules = {
    method: [{
      required: true,
      message: t('请选择处理方法'),
      trigger: 'change',
    }],
    new_operators: [{
      validator: (value: string[]) => formData.value.method !== 'transfer' || hasTransferOperators(value),
      message: t('转单人不能为空'),
      trigger: 'change',
    }],
    pa_id: [{
      validator: (value: string) => formData.value.method !== 'ProcessPackage' || Boolean(value),
      message: t('处理套餐不能为空'),
      trigger: 'change',
    }],
  };

  const {
    data: processApplicationList,
    loading: applicationLoading,
    run: fetchApplications,
  } = useRequest(ProcessApplicationManageService.fetchApplicationsAll, {
    defaultValue: [],
    manual: true,
  });

  const enabledApplications = computed(() => (
    processApplicationList.value.filter(item => item.is_enabled)
  ));

  const {
    loading: detailLoading,
    run: fetchDetail,
  } = useRequest(SoapManageService.fetchDetail, {
    defaultValue: {},
    manual: true,
    onSuccess(data: Record<string, PackageParam>) {
      const detail: Record<string, PackageParam> = {};
      const nextParams: Record<string, PackageParamValue> = {};
      Object.keys(data || {}).forEach((key) => {
        const item = data[key];
        const normalized = {
          ...item,
          key: item.key || key,
          type: 'self',
          is_hide: false,
        };
        detail[normalized.key] = normalized;
        nextParams[normalized.key] = { field: '', value: '' };
      });
      paramsDetailData.value = detail;
      formData.value.pa_params = nextParams;
    },
  });

  watch(() => formData.value.pa_params, () => {
    const nextDetail = { ...paramsDetailData.value };
    let detailChanged = false;
    Object.keys(nextDetail).forEach((key) => {
      const param = nextDetail[key];
      if (!Array.isArray(param.hide_condition)) {
        return;
      }
      let isHide = Boolean(param.is_hide);
      param.hide_condition.forEach((item) => {
        if (item.operator !== '=') {
          isHide = false;
          return;
        }
        const current = formData.value.pa_params[item.constant_key]?.value;
        isHide = String(item.value) === String(current ?? '');
      });
      if (isHide === param.is_hide) {
        return;
      }
      nextDetail[key] = { ...param, is_hide: isHide };
      detailChanged = true;
      if (isHide) {
        formData.value.pa_params[param.key] = { field: '', value: '' };
      }
    });
    if (detailChanged) {
      paramsDetailData.value = nextDetail;
    }
  }, { deep: true });

  const richTextLength = (html: string) => DOMPurify.sanitize(html || '', { ALLOWED_TAGS: [] }).trim().length;

  const resetForm = () => {
    formData.value = createForm();
    paramsDetailData.value = {};
    failures.value = [];
    editorKey.value += 1;
    formRef.value?.clearValidate?.();
  };

  const loadPackages = async () => {
    const packageEnabled = props.availability.actions.some(action => action.id === 'package' && action.enabled);
    if (!packageEnabled) {
      return;
    }
    if (props.scope === 'scene') {
      const sceneId = getSceneSystemParams().scope_id || props.availability.sceneIds[0];
      if (sceneId) {
        fetchApplications({ scene_id: sceneId });
      }
      return;
    }
    const { sceneIds } = props.availability;
    if (sceneIds.length <= 1) {
      if (sceneIds[0]) {
        fetchApplications({ scene_id: sceneIds[0] });
      }
      return;
    }
    packageMerging.value = true;
    try {
      const lists = await Promise.all(sceneIds.map(sceneId => (
        ProcessApplicationManageService.fetchApplicationsAll({ scene_id: sceneId })
      )));
      const merged = new Map<string, typeof lists[number][number]>();
      lists.flat().forEach((item) => {
        if (item?.id) {
          merged.set(String(item.id), item);
        }
      });
      processApplicationList.value = [...merged.values()];
    } finally {
      packageMerging.value = false;
    }
  };

  const {
    data: memberVariableSource,
    run: fetchMemberVariables,
  } = useRequest(MetaManageService.fetchVariableList, {
    defaultValue: [],
    manual: true,
  });

  const memberVariables = computed(() => {
    const list = Array.isArray(memberVariableSource.value) ? memberVariableSource.value : [];
    return list.map((item: { value?: string; label?: string }) => ({
      id: String(item.value || ''),
      name: `${item.value}(${item.label})`,
    })).filter(item => item.id);
  });

  const open = () => {
    resetForm();
    loadPackages();
    if (!memberVariables.value.length) {
      fetchMemberVariables();
    }
    isShow.value = true;
  };

  const handlePaIdChange = (id: string) => {
    const templateId = processApplicationList.value.find(item => item.id === id)?.sops_template_id;
    if (!templateId) {
      paramsDetailData.value = {};
      formData.value.pa_params = {};
      return;
    }
    fetchDetail({ id: String(templateId) });
  };

  const handleSubmit = async () => {
    try {
      await formRef.value?.validate?.();
    } catch {
      return;
    }
    const action = ACTION_BY_METHOD[formData.value.method];
    if (!props.riskIds.length || isSubmitting.value || !action) {
      return;
    }
    const description = formData.value.method === 'misreport'
      ? formData.value.misreport_description
      : formData.value.description;
    if (richTextLength(description) > 1000) {
      messageError(t('最多 1000 字'));
      return;
    }
    if (formData.value.method === 'ProcessPackage') {
      const visible = sortedParams.value.filter(item => item.show_type === 'show' && !item.is_hide);
      const filled = visible.every(item => isPackageParamFilled(formData.value.pa_params[item.key]));
      if (!filled) {
        messageError(t('套餐参数不能为空'));
        return;
      }
    }
    isSubmitting.value = true;
    failures.value = [];
    try {
      const receipt = await submitBatchProcess({
        action,
        riskIds: props.riskIds,
        description,
        transfer: {
          type: 'user',
          value: formData.value.new_operators,
        },
        paId: formData.value.pa_id,
        paParams: formData.value.pa_params,
        autoCloseRisk: formData.value.auto_close_risk,
      });
      if (receipt.failed.length) {
        failures.value = receipt.failed;
        return;
      }
      messageSuccess(t('操作成功'));
      isShow.value = false;
      emit('success');
    } catch {
      // 请求层已提示错误，弹窗保持打开
    } finally {
      isSubmitting.value = false;
    }
  };

  defineExpose({ open });
</script>

<style lang="postcss" scoped>
  .risk-await-deal-wrap {
    font-size: 12px;
  }

  .batch-process-hint {
    margin: 0 0 16px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
  }

  .misreport-alert {
    margin-bottom: 16px;
  }

  .risk-await-deal-wrap :deep(.bk-form),
  .risk-await-deal-wrap :deep(.bk-form-item),
  .risk-await-deal-wrap :deep(.bk-form-content) {
    width: 100%;
    max-width: 100%;
  }

  .risk-await-deal-wrap :deep(.bk-form-content) {
    line-height: 20px;
  }

  .risk-await-deal-wrap :deep(.bk-form-item) {
    margin-bottom: 16px;
  }

  .risk-await-deal-wrap :deep(.bk-form-item:last-child) {
    margin-bottom: 0;
  }

  .risk-await-deal-wrap :deep(.bk-form-error) {
    position: static;
    display: block;
    padding-top: 4px;
    line-height: 18px;
  }

  .risk-await-deal-wrap :deep(.bk-form-label) {
    padding-bottom: 0;
    margin-bottom: 6px;
    font-size: 12px;
    line-height: 20px;
    color: #313238;
  }

  .risk-await-deal-method__group {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 24px;
  }

  .risk-await-deal-method__group :deep(.bk-radio),
  .risk-await-deal-method__group :deep(.bk-radio .bk-radio-label) {
    font-size: 12px;
    font-weight: 400;
    line-height: 20px;
    color: #4d4f56;
  }

  .risk-await-deal-method__group :deep(.bk-radio.is-disabled),
  .risk-await-deal-method__group :deep(.bk-radio.is-disabled .bk-radio-label) {
    color: #c4c6cc;
    cursor: not-allowed;
  }

  .risk-await-deal-method__group :deep(.bk-radio.is-disabled .bk-radio-input) {
    cursor: not-allowed;
    background-color: #fafbfd;
    border-color: #dcdee5;
  }

  .risk-await-deal-wrap :deep(.bk-select),
  .risk-await-deal-wrap :deep(.bk-input),
  .risk-await-deal-wrap :deep(.transfer-user-selector),
  .risk-await-deal-wrap :deep(.pa-params-grid .bk-user-selector) {
    width: 100%;
  }

  .risk-await-deal-wrap :deep(.bk-user-selector) {
    min-width: 0;
  }

  .risk-await-deal-wrap :deep(.bk-user-selector .custom-tag) {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :deep(.await-deal-rich-editor),
  :deep(.await-deal-rich-editor .editor-wrap),
  :deep(.await-deal-rich-editor .quill-editor) {
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
  }

  :deep(.await-deal-rich-editor .ql-container) {
    min-height: 180px;
  }

  .process-package-select-item {
    margin-bottom: 0 !important;
  }

  .pa-params-form-item {
    margin-top: 24px !important;
    margin-bottom: 0 !important;
  }

  .pa-params-form-item :deep(.bk-form-content) {
    max-width: 100%;
  }

  .auto-close-risk-form-item {
    margin-top: 24px !important;
    margin-bottom: 0 !important;
  }

  .pa-params-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
    padding: 16px 12px;
    background: #f0f1f5;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .pa-params-grid :deep(.bk-select),
  .pa-params-grid :deep(.bk-input:not(textarea, .bk-textarea)),
  .pa-params-grid :deep(.bk-date-picker),
  .pa-params-grid :deep(.bk-date-picker-rel),
  .pa-params-grid :deep(.bk-date-picker-editor),
  .pa-params-grid :deep(.pa-user-selector.bk-user-selector),
  .pa-params-grid :deep(.pa-user-selector .user-selector-input) {
    height: 32px;
    max-height: 32px;
    min-height: 32px;
    box-sizing: border-box;
  }

  .pa-params-grid :deep(.field-insert-wrapper:not(.is-textarea).has-suffix) {
    height: 32px;
    align-items: center;
  }

  .pa-params-grid :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__main),
  .pa-params-grid :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__control),
  .pa-params-grid :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__suffix-host),
  .pa-params-grid :deep(.field-insert-wrapper:not(.is-textarea) .field-insert-wrapper__suffix) {
    height: 32px;
    max-height: 32px;
    min-height: 32px;
    box-sizing: border-box;
  }

  .pa-params-field {
    width: 100%;
    margin-bottom: 0 !important;
  }

  .pa-params-field :deep(.bk-form-item) {
    display: block;
  }

  .pa-params-field :deep(.bk-form-label) {
    width: 100% !important;
    padding-bottom: 0;
    text-align: left;
  }

  .pa-params-field :deep(.bk-form-label::after) {
    display: none;
  }

  .pa-params-field :deep(.bk-form-content) {
    max-width: 100%;
    min-width: 0;
    margin-left: 0 !important;
  }

  .label-name::after {
    margin-left: 5px;
    color: #ea3636;
    content: '*';
  }

  .underline {
    border-bottom: 1px dashed #c4c6cc;
  }

  .batch-process-failures {
    margin-top: 16px;
    font-size: 12px;
    line-height: 20px;
    color: #ea3636;
  }
</style>
