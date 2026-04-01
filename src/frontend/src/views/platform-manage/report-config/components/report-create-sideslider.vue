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
              <bk-cascader
                v-model="formData.vision_id"
                children-key="share"
                id-key="uid"
                :list="Array.isArray(chartLists) ? chartLists : []"
                :multiple="false"
                :show-complete-name="false"
                style="width: 500px;"
                trigger="click"
                @change="handleSpaceChange" />
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

  import ReportConfigService from '@service/report-config';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  export interface ReportGroup {
    id: number;
    name: string;
  }

  export interface ReportFormData {
    id?: string;
    bkvisionReport: string;
    name: string;
    groupId: number | null;
    description: string;
    enabled: boolean;
    vision_id: string[];
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
    groupList?: ReportGroup[];
    defaultGroupId?: number | null;
    editData?: ReportFormData | null;
    chartLists?: ChartListModel[];
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'submit', data: ReportFormData): void;
    (e: 'cancel'): void;
    (e: 'success'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    groupList: () => [],
    defaultGroupId: null,
    editData: null,
    chartLists: () => [],
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 是否编辑模式
  const isEditMode = computed(() => !!props.editData);

  // 图表列表数据（从 props 获取）
  const chartLists = computed(() => props.chartLists || []);
  const { messageSuccess } = useMessage();

  // 表单引用
  const formRef = ref();

  // 表单数据
  const formData = ref<ReportFormData>({
    bkvisionReport: '',
    vision_id: [],
    name: '',
    groupId: null,
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

  // 根据子级 uid 查找完整的级联路径
  const findCascaderPath = (targetUid: string): string[] => {
    for (const parent of chartLists.value) {
      if (parent.share) {
        const child = parent.share.find(item => item.uid === targetUid);
        if (child) {
          return [parent.uid, child.uid];
        }
      }
    }
    return [];
  };

  // 监听显示状态，重置表单
  watch(() => props.isShow, (val) => {
    if (val) {
      if (props.editData) {
        // 编辑模式，填充数据
        formData.value = { ...props.editData };
        // 如果有 bkvisionReport，需要等待 chartLists 加载后设置完整路径
        if (props.editData.bkvisionReport && chartLists.value.length > 0) {
          formData.value.vision_id = findCascaderPath(props.editData.bkvisionReport);
        }
      } else {
        // 新建模式，重置表单
        formData.value = {
          bkvisionReport: '',
          vision_id: [],
          name: '',
          groupId: props.defaultGroupId ?? null,
          description: '',
          enabled: false,
        };
      }
    }
  });

  // 监听 chartLists 加载完成，编辑模式下设置级联选择器的值
  watch(() => chartLists.value, (newChartLists) => {
    if (newChartLists.length > 0 && props.isShow && props.editData?.bkvisionReport) {
      formData.value.vision_id = findCascaderPath(props.editData.bkvisionReport);
    }
  });

  // 级联选择器变化处理
  const handleSpaceChange = (value: string[], _: unknown, selectedOptions: Record<string, string>[]) => {
    if (value && value.length > 0) {
      // 获取最后一级选中的值作为 bkvisionReport
      formData.value.bkvisionReport = value[value.length - 1];
      // 如果报表名称为空，自动填充选中的报表名称
      if (!formData.value.name && selectedOptions && selectedOptions.length > 0) {
        const lastOption = selectedOptions[selectedOptions.length - 1];
        if (lastOption?.name) {
          formData.value.name = lastOption.name;
        }
      }
    } else {
      formData.value.bkvisionReport = '';
    }
  };

  // 预览报表
  const handlePreview = () => {
    if (formData.value.bkvisionReport) {
      // 根据选中的报表ID跳转到预览页面
      // TODO: 根据实际的预览URL格式调整
      const previewUrl = `/bkvision/preview/${formData.value.bkvisionReport}`;
      window.open(previewUrl, '_blank');
    }
  };

  // 创建 Panel
  const {
    run: createPanel,
    loading: createLoading,
  } = useRequest(ReportConfigService.createPanel, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('创建成功'));
      emit('success'); // 通知父组件刷新列表
      handleClose();
    },
  });

  // 更新 Panel
  const {
    run: updatePanel,
    loading: updateLoading,
  } = useRequest(ReportConfigService.updatePanel, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('更新成功'));
      emit('success'); // 通知父组件刷新列表
      handleClose();
    },
  });

  // 提交 loading
  const submitLoading = computed(() => createLoading.value || updateLoading.value);

  // 提交
  const handleSubmit = async () => {
    formRef.value?.validate().then(() => {
      // 找到选中分组的名称
      const selectedGroup = props.groupList.find(g => g.id === formData.value.groupId);
      const groupName = selectedGroup?.name || '';
      // 获取级联选择器选中的最后一级值（报表ID）
      const visionId = formData.value.vision_id.length > 0
        ? formData.value.vision_id[formData.value.vision_id.length - 1]
        : '';

      if (isEditMode.value && formData.value.id) {
        // 编辑模式，调用 updatePanel API
        updatePanel({
          id: formData.value.id,
          vision_id: visionId,
          name: formData.value.name,
          group_name: groupName,
          description: formData.value.description || undefined,
          is_enabled: formData.value.enabled,
        });
      } else {
        // 创建模式，调用 createPanel API
        createPanel({
          vision_id: visionId,
          name: formData.value.name,
          group_name: groupName,
          description: formData.value.description,
          is_enabled: formData.value.enabled,
        });
      }
    });
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

  :deep(.bk-cascader) {
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
