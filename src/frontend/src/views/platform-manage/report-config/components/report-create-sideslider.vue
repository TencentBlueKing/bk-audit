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
  <bk-sideslider
    :is-show="isShow"
    :quick-close="false"
    show-mask
    :title="isEditMode ? t('编辑报表') : t('新建报表')"
    :width="640"
    :z-index="9999"
    @closed="handleSliderClosed">
    <template #default>
      <div class="report-create-content">
        <bk-form
          ref="formRef"
          class="report-create-form"
          form-type="vertical"
          :model="formData"
          :rules="formRules">
          <!-- 关联 BKVision 报表 -->
          <bk-form-item
            :label="t('关联 BKVision 报表')"
            property="bkvisionReport"
            required>
            <div class="bkvision-select-wrapper">
              <bk-select
                v-model="formData.bkvisionReport"
                :clearable="false"
                filterable
                :placeholder="t('选择项目')"
                :popover-options="{
                  boundary: 'parent',
                  zIndex: 9999
                }"
                style="width: 500px;"
                @change="handleReportChange">
                <bk-option-group
                  v-for="group in chartGroupedLists"
                  :key="group.uid"
                  collapsible
                  :label="group.name">
                  <bk-option
                    v-for="item in group.share"
                    :id="item.uid"
                    :key="item.uid"
                    :name="`【${group.name}】${item.name}`">
                    <template #default>
                      <div class="report-option-content">
                        <span class="option-name">{{ item.name }}</span>
                        <audit-icon
                          class="preview-icon"
                          type="jump-link"
                          @click.stop="handlePreviewReport(item)" />
                      </div>
                    </template>
                  </bk-option>
                </bk-option-group>
              </bk-select>
              <bk-button
                v-if="formData.bkvisionReport"
                class="preview-btn"
                @click="handlePreview">
                {{ t('预览') }}
                <audit-icon
                  class="ml4"
                  type="jump-link" />
              </bk-button>
            </div>
          </bk-form-item>

          <!-- 报表名称 -->
          <bk-form-item
            :label="t('报表名称')"
            property="name"
            required>
            <bk-input
              v-model="formData.name"
              :placeholder="t('请输入报表名称（选择报表后自动填充）')"
              @change="handleNameChange" />
          </bk-form-item>

          <!-- 可见范围 -->
          <bk-form-item
            :label="t('可见范围')"
            property="visibility_type"
            required>
            <visible-range-field
              :form-data="visibilityFormData"
              match-selector-width
              popover-class="is-compact"
              @update:form-data="handleVisibleRangeChange" />
          </bk-form-item>

          <!-- 描述 -->
          <bk-form-item
            :label="t('描述')"
            property="description">
            <bk-input
              v-model="formData.description"
              :maxlength="100"
              :placeholder="t('请输入')"
              :rows="3"
              show-word-limit
              type="textarea" />
          </bk-form-item>

          <!-- 是否启用 -->
          <bk-form-item
            :label="t('是否启用')"
            property="status">
            <div class="status-field">
              <bk-switcher
                v-model="formData.enabled"
                size="small"
                theme="primary" />
              <span class="status-label">{{ formData.enabled ? t('启用') : t('停用') }}</span>
            </div>
          </bk-form-item>
        </bk-form>
      </div>
    </template>
    <template #footer>
      <bk-button
        class="mr8"
        :loading="submitLoading"
        theme="primary"
        @click="handleSubmit">
        {{ t('提交') }}
      </bk-button>
      <bk-button @click="handleClose">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-sideslider>
</template>

<script setup lang='ts'>
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ReportConfigService from '@service/report-config';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';
  import type { PanelVisibilityType } from '@model/report-config/panel';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import VisibleRangeField from '@views/platform-manage/tool-manage/create-tool/components/visible-range-field.vue';
  import {
    applyVisibilityToFormData,
    buildVisibilityPayload,
    shouldSubmitVisibilityPayload,
  } from '@views/platform-manage/tool-manage/create-tool/submit-payload';
  import type { FormData as ToolFormData } from '@views/platform-manage/tool-manage/create-tool/types';

  export interface ReportFormData {
    id?: string;
    bkvisionReport: string;
    name: string;
    description: string;
    status?: 'published' | 'unpublished';
    enabled: boolean;
    visibility_type: PanelVisibilityType;
    scene_ids: number[];
    system_ids: string[];
  }

  interface ChartListModel {
    uid: string;
    name: string;
    share: Array<{
      uid: string;
      name: string;
    }>;
  }

  interface Props {
    isShow: boolean;
    editData?: ReportFormData | null;
    chartLists?: ChartListModel[];
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'submit', data: ReportFormData): void;
    (e: 'cancel'): void;
    (e: 'success', panelId?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    editData: null,
    chartLists: () => [],
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const isEditMode = computed(() => !!props.editData);
  const chartLists = computed(() => props.chartLists || []);
  const chartGroupedLists = computed(() => chartLists.value);
  const { messageSuccess } = useMessage();
  const formRef = ref();

  const formData = ref<ReportFormData>({
    bkvisionReport: '',
    name: '',
    description: '',
    enabled: false,
    visibility_type: 'all_visible',
    scene_ids: [],
    system_ids: [],
  });

  const visibilityFormData = computed(() => ({
    name: formData.value.name,
    tags: [],
    description: formData.value.description,
    tool_type: '',
    updated_at: '',
    updated_by: '',
    is_bkvision: true,
    updated_time: null,
    data_search_config_type: '',
    visibility_type: formData.value.visibility_type,
    scene_ids: formData.value.scene_ids,
    system_ids: formData.value.system_ids,
    config: {
      referenced_tables: [],
      input_variable: [],
      output_fields: [],
      sql: '',
      uid: '',
      output_config: {
        enable_grouping: false,
        groups: [],
      },
    },
  } as ToolFormData));

  const formRules = {
    bkvisionReport: [
      {
        required: true,
        message: t('请选择关联 BKVision 报表'),
        trigger: 'blur',
      },
    ],
    name: [
      {
        required: true,
        message: t('请输入报表名称'),
        trigger: 'blur',
      },
    ],
    visibility_type: [
      {
        validator: () => shouldSubmitVisibilityPayload(formData.value),
        message: t('请选择可见范围'),
        trigger: 'change',
      },
    ],
  };

  const handleNameChange = () => {
    formRef.value?.validate('name');
  };

  const handleVisibleRangeChange = (value: ToolFormData) => {
    formData.value = {
      ...formData.value,
      visibility_type: value.visibility_type,
      scene_ids: value.scene_ids || [],
      system_ids: value.system_ids || [],
    };
    formRef.value?.validate('visibility_type');
  };

  const fillEditFormData = (data: ReportFormData) => {
    const visibilityData = applyVisibilityToFormData({
      visibility_type: data.visibility_type,
      scene_ids: data.scene_ids,
      system_ids: data.system_ids,
    }) || {
      visibility_type: 'all_visible' as PanelVisibilityType,
      scene_ids: [],
      system_ids: [],
    };
    formData.value = {
      id: data.id,
      bkvisionReport: data.bkvisionReport || '',
      name: data.name,
      description: data.description === '--' ? '' : (data.description || ''),
      status: data.status || 'unpublished',
      enabled: (data.status ?? 'unpublished') === 'published',
      visibility_type: visibilityData.visibility_type,
      scene_ids: visibilityData.scene_ids,
      system_ids: visibilityData.system_ids,
    };
  };

  const resetCreateFormData = () => {
    formData.value = {
      bkvisionReport: '',
      name: '',
      description: '',
      enabled: false,
      visibility_type: 'all_visible',
      scene_ids: [],
      system_ids: [],
    };
  };

  watch(() => props.isShow, (val) => {
    if (val) {
      if (props.editData) {
        fillEditFormData(props.editData);
      } else {
        resetCreateFormData();
      }
      nextTick(() => {
        formRef.value?.clearValidate();
        setTimeout(() => {
          formRef.value?.clearValidate();
        }, 100);
      });
    }
  });

  watch(() => props.editData, (data) => {
    if (props.isShow && data) {
      fillEditFormData(data);
    } else if (props.isShow && !data) {
      resetCreateFormData();
    }
  });

  const handleReportChange = (value: string) => {
    if (value) {
      formData.value.bkvisionReport = value;
      for (const group of chartLists.value) {
        if (group.share) {
          const report = group.share.find(item => item.uid === value);
          if (report?.name) {
            formData.value.name = report.name;
            break;
          }
        }
      }
    } else {
      formData.value.bkvisionReport = '';
      formData.value.name = '';
    }
    formRef.value?.validate('bkvisionReport');
    formRef.value?.validate('name');
  };

  const handlePreviewReport = async (item: { uid: string; name: string }) => {
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      const res = await fetchReportDetail({
        share_uid: item.uid,
      });
      if (res && res.data?.dashboard_uid) {
        let spaceUid = '';
        for (const group of chartLists.value) {
          if (group.share?.find(i => i.uid === item.uid)) {
            spaceUid = group.uid;
            break;
          }
        }
        window.open(`${baseUrl}#/${spaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
      }
    } catch (e) {
      console.error('获取报表详情失败:', e);
    }
  };

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const {
    run: fetchReportDetail,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: null,
  });

  const handlePreview = async () => {
    if (!formData.value.bkvisionReport) return;
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      const res = await fetchReportDetail({
        share_uid: formData.value.bkvisionReport,
      });
      if (res && res.data?.dashboard_uid) {
        let spaceUid = '';
        for (const group of chartLists.value) {
          const report = group.share?.find(item => item.uid === formData.value.bkvisionReport);
          if (report) {
            spaceUid = group.uid;
            break;
          }
        }
        window.open(`${baseUrl}#/${spaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
      }
    } catch (e) {
      console.error('获取报表详情失败:', e);
    }
  };

  const {
    run: createPlatformPanel,
    loading: createLoading,
  } = useRequest(ReportConfigService.createPlatformPanel, {
    defaultValue: null,
    onSuccess: (res: any) => {
      messageSuccess(t('创建成功'));
      emit('success', res?.id);
      handleClose();
    },
  });

  const {
    run: updatePlatformPanel,
    loading: updateLoading,
  } = useRequest(ReportConfigService.updatePlatformPanel, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('更新成功'));
      emit('success');
      handleClose();
    },
  });

  const submitLoading = computed(() => createLoading.value || updateLoading.value);

  const buildSubmitPayload = () => {
    const payload: Record<string, any> = {
      vision_id: formData.value.bkvisionReport,
      name: formData.value.name,
      status: formData.value.enabled ? 'published' : 'unpublished',
      description: formData.value.description || undefined,
    };

    if (shouldSubmitVisibilityPayload(formData.value)) {
      payload.visibility = buildVisibilityPayload(formData.value);
    }

    return payload;
  };

  const handleSubmit = async () => {
    formRef.value?.validate().then(() => {
      const payload = buildSubmitPayload();

      if (isEditMode.value && formData.value.id) {
        updatePlatformPanel({
          panel_id: formData.value.id,
          ...payload,
        });
      } else {
        createPlatformPanel(payload);
      }
    });
  };

  const handleSliderClosed = () => {
    emit('update:isShow', false);
  };

  const handleClose = () => {
    emit('update:isShow', false);
    emit('cancel');
  };
</script>

<style lang="postcss" scoped>
.report-create-content {
  padding: 24px 40px;
}

.ml4 {
  margin-left: 4px;
}

.mr8 {
  margin-right: 8px;
}

.bkvision-select-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;

  :deep(.bk-select) {
    flex: 1;
  }

  .preview-btn {
    flex-shrink: 0;
    color: #3a84ff;

    &:hover {
      color: #699df4;
    }
  }
}

.report-option-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .option-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .preview-icon {
    margin-left: 8px;
    color: #3a84ff;
    cursor: pointer;

    &:hover {
      color: #699df4;
    }
  }
}

.status-field {
  display: flex;
  align-items: center;
  margin-bottom: 8px;

  .status-label {
    margin-left: 8px;
    font-size: 12px;
    color: #63656e;
  }
}

.report-create-form {
  :deep(.bk-form-label) {
    font-size: 12px;
  }
}
</style>
