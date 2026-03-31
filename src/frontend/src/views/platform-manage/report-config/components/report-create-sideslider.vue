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
    :title="isEditMode ? t('编辑报表') : t('新建报表')"
    :width="640"
    @closed="handleClose">
    <template #default>
      <div class="report-create-content">
        <bk-form
          ref="formRef"
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
                class="bkvision-select"
                filterable
                :placeholder="t('请选择')"
                @change="handleBkvisionReportChange">
                <bk-option
                  v-for="item in bkvisionReportList"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id" />
              </bk-select>
              <bk-button
                class="preview-btn"
                :disabled="!formData.bkvisionReport"
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
              :placeholder="t('请输入报表名称（选择报表后自动填充）')" />
          </bk-form-item>

          <!-- 所属分组 -->
          <bk-form-item
            :label="t('所属分组')"
            property="groupId"
            required>
            <bk-select
              v-model="formData.groupId"
              :placeholder="t('请选择')">
              <bk-option
                v-for="group in groupList"
                :key="group.id"
                :label="group.name"
                :value="group.id" />
            </bk-select>
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
              <span class="status-tip">
                <audit-icon
                  class="mr4"
                  type="info" />
                {{ t('停用后将在审计报表菜单中隐藏') }}
              </span>
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
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  export interface ReportGroup {
    id: string;
    name: string;
  }

  export interface BkvisionReport {
    id: string;
    name: string;
    url?: string;
  }

  export interface ReportFormData {
    bkvisionReport: string;
    name: string;
    groupId: string;
    description: string;
    enabled: boolean;
  }

  interface Props {
    isShow: boolean;
    groupList?: ReportGroup[];
    bkvisionReportList?: BkvisionReport[];
    defaultGroupId?: string;
    editData?: ReportFormData | null;
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'submit', data: ReportFormData): void;
    (e: 'cancel'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    groupList: () => [],
    bkvisionReportList: () => [],
    defaultGroupId: '',
    editData: null,
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 是否编辑模式
  const isEditMode = computed(() => !!props.editData);

  // 表单引用
  const formRef = ref();
  const submitLoading = ref(false);

  // 表单数据
  const formData = ref<ReportFormData>({
    bkvisionReport: '',
    name: '',
    groupId: '',
    description: '',
    enabled: false,
  });

  // 表单校验规则
  const formRules = {
    bkvisionReport: [
      {
        required: true,
        message: t('请选择关联 BKVision 报表'),
        trigger: 'change',
      },
    ],
    name: [
      {
        required: true,
        message: t('请输入报表名称'),
        trigger: 'blur',
      },
    ],
    groupId: [
      {
        required: true,
        message: t('请选择所属分组'),
        trigger: 'change',
      },
    ],
  };

  // 监听显示状态，重置表单
  watch(() => props.isShow, (val) => {
    if (val) {
      if (props.editData) {
        // 编辑模式，填充数据
        formData.value = { ...props.editData };
      } else {
        // 新建模式，重置表单
        formData.value = {
          bkvisionReport: '',
          name: '',
          groupId: props.defaultGroupId || '',
          description: '',
          enabled: false,
        };
      }
    }
  });

  // 选择 BKVision 报表后自动填充名称
  const handleBkvisionReportChange = (value: string) => {
    const selectedReport = props.bkvisionReportList.find(item => item.id === value);
    if (selectedReport && !formData.value.name) {
      formData.value.name = selectedReport.name;
    }
  };

  // 预览报表
  const handlePreview = () => {
    const selectedReport = props.bkvisionReportList.find(item => item.id === formData.value.bkvisionReport);
    if (selectedReport?.url) {
      window.open(selectedReport.url, '_blank');
    }
  };

  // 提交
  const handleSubmit = async () => {
    try {
      await formRef.value?.validate();
      submitLoading.value = true;
      emit('submit', { ...formData.value });
      submitLoading.value = false;
    } catch {
      // 表单验证失败
    }
  };

  // 关闭
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

.mr4 {
  margin-right: 4px;
}

.mr8 {
  margin-right: 8px;
}

.bkvision-select-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;

  .bkvision-select {
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

.status-field {
  display: flex;
  align-items: center;
  margin-bottom: 8px;

  .status-tip {
    display: flex;
    align-items: center;
    margin-right: 16px;
    font-size: 12px;
    color: #979ba5;
  }

  .status-label {
    margin-left: 8px;
    font-size: 12px;
    color: #63656e;
  }
}

</style>
