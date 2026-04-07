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
            <div class="group-select-wrapper">
              <bk-select
                v-model="formData.groupId"
                :placeholder="t('请选择')"
                style="flex: 1;">
                <bk-option
                  v-for="group in allGroupList"
                  :key="group.id"
                  :label="group.name"
                  :value="group.id" />
              </bk-select>
              <bk-button
                text
                theme="primary"
                @click="handleShowAddGroup">
                {{ t('新增分组') }}
              </bk-button>
            </div>
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

  <!-- 新增分组弹窗 -->
  <bk-dialog
    v-model:is-show="addGroupDialogVisible"
    :title="t('新建分组')"
    width="480">
    <bk-form
      ref="addGroupFormRef"
      form-type="vertical"
      :model="addGroupFormData"
      :rules="addGroupFormRules">
      <bk-form-item
        :label="t('分组名称')"
        property="name"
        required>
        <bk-input
          v-model="addGroupFormData.name"
          :placeholder="t('请输入')" />
      </bk-form-item>
    </bk-form>
    <template #footer>
      <bk-button
        class="mr8"
        :loading="addGroupLoading"
        theme="primary"
        @click="handleConfirmAddGroup">
        {{ t('确定') }}
      </bk-button>
      <bk-button @click="handleCancelAddGroup">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang='ts'>
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ReportConfigService from '@service/report-config';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';

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

  // 新增分组相关状态
  const addGroupDialogVisible = ref(false);
  const addGroupFormRef = ref();
  const addGroupLoading = ref(false);
  const addGroupFormData = ref({
    name: '',
  });
  const addGroupFormRules = {
    name: [
      {
        required: true,
        message: t('分组名称不能为空'),
        trigger: 'blur',
      },
    ],
  };

  // 本地新增的分组列表
  const localGroupList = ref<ReportGroup[]>([]);

  // 合并原有分组和本地新增的分组
  const allGroupList = computed(() => [...localGroupList.value, ...props.groupList]);

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
        trigger: 'change',
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
  const handleSpaceChange = (value: string[]) => {
    if (value && value.length > 0) {
      // 获取最后一级选中的值作为 bkvisionReport
      const reportUid = value[value.length - 1];
      formData.value.bkvisionReport = reportUid;

      // 从 chartLists 中查找报表名称并自动填充
      const spaceUid = value[0];
      const space = chartLists.value.find(item => item.uid === spaceUid);
      if (space?.share) {
        const report = space.share.find(item => item.uid === reportUid);
        if (report?.name) {
          formData.value.name = report.name;
        }
      }
    } else {
      formData.value.bkvisionReport = '';
      formData.value.name = '';
    }
  };

  // 获取配置数据（用于获取 BKVision URL）
  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  // 获取报表详情（用于获取 dashboard_uid）
  const {
    run: fetchReportDetail,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: null,
  });

  // 预览报表
  const handlePreview = async () => {
    if (!formData.value.bkvisionReport || formData.value.vision_id.length === 0) return;
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      // 先调用接口获取 dashboard_uid
      const res = await fetchReportDetail({
        share_uid: formData.value.bkvisionReport,
      });
      if (res && res.data?.dashboard_uid) {
        // 获取空间 ID（级联选择器的第一个值）
        const spaceUid = formData.value.vision_id[0];
        // 构建跳转链接：baseUrl#/spaceUid/dashboards/detail/root/dashboardUid
        window.open(`${baseUrl}#/${spaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
      }
    } catch (e) {
      console.error('获取报表详情失败:', e);
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
      // 从 allGroupList 中查找选中分组的名称（包括本地新增的分组）
      const selectedGroup = allGroupList.value.find(g => g.id === formData.value.groupId);
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
    // 重置新增分组状态
    localGroupList.value = [];
  };

  // 显示新增分组弹窗
  const handleShowAddGroup = () => {
    addGroupFormData.value.name = '';
    addGroupDialogVisible.value = true;
  };

  // 确认新增分组
  const handleConfirmAddGroup = async () => {
    try {
      await addGroupFormRef.value?.validate();
      addGroupLoading.value = true;

      // 检查分组名称是否已存在
      const exists = allGroupList.value.some(g => g.name === addGroupFormData.value.name.trim());
      if (exists) {
        messageSuccess(t('分组名称已存在'));
        addGroupLoading.value = false;
        return;
      }

      // 生成临时 ID（负数表示本地新增的分组）
      const tempId = -(Date.now());
      const newGroup: ReportGroup = {
        id: tempId,
        name: addGroupFormData.value.name.trim(),
      };

      // 添加到本地分组列表
      localGroupList.value.push(newGroup);

      // 自动选中新增的分组
      formData.value.groupId = tempId;

      // 关闭弹窗
      addGroupDialogVisible.value = false;
      addGroupFormData.value.name = '';
      addGroupLoading.value = false;
    } catch {
      // 表单验证失败
      addGroupLoading.value = false;
    }
  };

  // 取消新增分组
  const handleCancelAddGroup = () => {
    addGroupDialogVisible.value = false;
    addGroupFormData.value.name = '';
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

.group-select-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

</style>
