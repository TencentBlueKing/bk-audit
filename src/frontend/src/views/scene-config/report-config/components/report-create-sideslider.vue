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

          <!-- 所属分组 -->
          <bk-form-item
            :label="t('所属分组')"
            property="groupId"
            required>
            <bk-select
              v-model="formData.groupId"
              :clearable="false"
              :placeholder="t('请选择')"
              :popover-options="{
                boundary: 'parent',
                zIndex: 9999
              }"
              style="flex: 1;"
              @change="handleGroupChange">
              <bk-option
                v-for="group in groupList"
                :key="group.id"
                :label="group.name"
                :value="group.id" />
              <template #extension>
                <div
                  class="create-group-btn"
                  @click="handleCreateGroup">
                  <audit-icon type="plus-circle" />
                  {{ t('新建分组') }}
                </div>
              </template>
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

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

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
    status?: 'published' | 'unpublished';
    enabled: boolean;
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
    defaultGroupName?: string | null;
    editData?: ReportFormData | null;
    chartLists?: ChartListModel[];
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'submit', data: ReportFormData): void;
    (e: 'cancel'): void;
    (e: 'success', panelId?: string): void;
    (e: 'create-group'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    groupList: () => [],
    defaultGroupId: null,
    defaultGroupName: null,
    editData: null,
    chartLists: () => [],
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 是否编辑模式
  const isEditMode = computed(() => !!props.editData);

  // 图表列表数据（从 props 获取）
  const chartLists = computed(() => props.chartLists || []);

  // 分组后的图表列表（用于下拉框展示）
  const chartGroupedLists = computed(() => chartLists.value);

  const { messageSuccess } = useMessage();

  // 表单引用
  const formRef = ref();

  // 表单数据
  const formData = ref<ReportFormData>({
    bkvisionReport: '',
    name: '',
    groupId: null,
    description: '',
    enabled: false,
  });

  // 新建模式，重置表单
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
    groupId: [
      {
        required: true,
        message: t('请选择所属分组'),
        trigger: 'blur',
      },
    ],
  };
  const handleNameChange = () => {
    formRef.value?.validate('name');
  };
  const handleGroupChange = () => {
    formRef.value?.validate('groupId');
  };

  // 新建分组
  const handleCreateGroup = () => {
    emit('create-group');
  };
  // 填充编辑数据的通用逻辑
  const fillEditFormData = (data: ReportFormData) => {
    formData.value = {
      id: data.id,
      bkvisionReport: data.bkvisionReport || '',
      name: data.name,
      groupId: data.groupId ?? null,
      description: data.description || '--',
      status: data.status || 'unpublished',
      enabled: (data.status ?? 'unpublished') === 'published',
    };
  };

  // 重置新建模式表单
  const resetCreateFormData = () => {
    let defaultGroupIdValue = props.defaultGroupId ?? null;
    if (props.defaultGroupName) {
      const matchedGroup = props.groupList.find(g => g.name === props.defaultGroupName);
      if (matchedGroup) {
        defaultGroupIdValue = matchedGroup.id;
      }
    }
    formData.value = {
      bkvisionReport: '',
      name: '',
      groupId: defaultGroupIdValue,
      description: '',
      enabled: false,
    };
  };

  // 监听显示状态，重置/填充表单
  watch(() => props.isShow, (val) => {
    if (val) {
      if (props.editData) {
        fillEditFormData(props.editData);
      } else {
        resetCreateFormData();
      }
      // 打开时清除校验状态，避免立即显示错误提示
      nextTick(() => {
        formRef.value?.clearValidate();
        // 再次确保清除（解决某些情况下 clearValidate 不生效的问题）
        setTimeout(() => {
          formRef.value?.clearValidate();
        }, 100);
      });
    }
  });

  // 监听 editData 变化（双重保障，解决 isShow 与 editData 更新时序竞态问题）
  watch(() => props.editData, (data) => {
    if (props.isShow && data) {
      fillEditFormData(data);
    } else if (props.isShow && !data) {
      resetCreateFormData();
    }
  });

  // 监听 defaultGroupId 变化（新建分组成功后自动选中新建的分组）
  watch(() => props.defaultGroupId, (newId) => {
    if (props.isShow && newId !== null && !props.editData) {
      formData.value.groupId = newId;
    }
  });

  // 监听 chartLists 加载完成，编辑模式下设置选择器的值
  // bkvisionReport 直接存储 uid，无需额外处理

  // 报表选择变化处理
  const handleReportChange = (value: string) => {
    if (value) {
      formData.value.bkvisionReport = value;
      // 从 chartLists 中查找报表名称并自动填充
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

  // 预览报表（点击选项右侧图标）
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
    if (!formData.value.bkvisionReport) return;
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    if (!baseUrl) return;

    try {
      // 先调用接口获取 dashboard_uid
      const res = await fetchReportDetail({
        share_uid: formData.value.bkvisionReport,
      });
      if (res && res.data?.dashboard_uid) {
        // 从 chartLists 中查找空间 uid
        let spaceUid = '';
        for (const group of chartLists.value) {
          const report = group.share?.find(item => item.uid === formData.value.bkvisionReport);
          if (report) {
            spaceUid = group.uid;
            break;
          }
        }
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
    onSuccess: (res: any) => {
      messageSuccess(t('创建成功'));
      emit('success', res?.id); // 通知父组件刷新列表，并传递新建报表ID用于高亮
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
      // 从 groupList 中查找选中分组的名称
      const selectedGroup = props.groupList.find(g => g.id === formData.value.groupId);
      const groupId = selectedGroup?.id || '';
      // 直接使用 bkvisionReport 作为 vision_id
      const visionId = formData.value.bkvisionReport;

      if (isEditMode.value && formData.value.id) {
        // 编辑模式，调用 updatePanel API
        updatePanel({
          id: formData.value.id,
          scene_id: getSceneSystemParams().scope_id,
          group_id: typeof groupId === 'number' ? groupId : Number(groupId),
          panel_id: formData.value.id,
          vision_id: visionId,
          name: formData.value.name,
          status: formData.value.enabled ? 'published' : 'unpublished',
          description: formData.value.description || undefined,
        });
      } else {
        // 创建模式，调用 createPanel API
        createPanel({
          vision_id: visionId,
          name: formData.value.name,
          group_id: groupId,
          status: formData.value.enabled ? 'published' : 'unpublished',
          description: formData.value.description,
          scene_id: getSceneSystemParams().scope_id,
        });
      }
    });
  };

  // 侧边栏关闭（箭头/遮罩点击），仅关闭弹窗
  const handleSliderClosed = () => {
    emit('update:isShow', false);
  };

  // 取消按钮关闭，同时通知父组件
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

.create-group-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 40px;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
  border-top: 1px solid #dcdee5;

  &:hover {
    background-color: #f5f7fa;
  }
}

.report-create-form {
  :deep(.bk-form-label) {
    font-size: 12px;
  }
}
</style>
