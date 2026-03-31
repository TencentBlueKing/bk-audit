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
  <div class="report-group-list">
    <vuedraggable
      v-model="localGroups"
      class="report-collapse"
      handle=".group-drag-handle"
      item-key="id"
      @end="handleGroupDragEnd">
      <template #item="{ element: group }">
        <bk-collapse
          v-model="activeGroups"
          class="group-collapse-item"
          use-card-theme>
          <bk-collapse-panel
            :key="group.id"
            :name="group.id">
            <template #header>
              <div class="collapse-header">
                <div class="collapse-header-left">
                  <audit-icon
                    class="group-drag-handle drag-icon mr8"
                    type="move" />
                  <audit-icon
                    class="expand-icon mr8"
                    :class="{ expanded: activeGroups.includes(group.id) }"
                    type="angle-fill-down" />
                  <span class="group-name">{{ group.name }}</span>
                  <span class="group-count">{{ group.reports.length }}</span>
                </div>
                <div
                  class="collapse-header-right"
                  @click.stop>
                  <bk-button
                    text
                    theme="primary"
                    @click="handleAddReport(group.id)">
                    <audit-icon
                      class="mr4"
                      type="plus-circle" />
                    {{ t('新建报表') }}
                  </bk-button>
                  <bk-dropdown>
                    <bk-button
                      class="group-more-btn"
                      text>
                      <audit-icon type="more" />
                    </bk-button>
                    <template #content>
                      <bk-dropdown-menu>
                        <bk-dropdown-item @click="handleShowRenameDialog(group)">
                          {{ t('重命名') }}
                        </bk-dropdown-item>
                      </bk-dropdown-menu>
                    </template>
                  </bk-dropdown>
                </div>
              </div>
            </template>
            <template #content>
              <primary-table
                :columns="tableColumns as any"
                :data="group.reports"
                drag-sort="row-handler"
                row-key="id"
                @drag-sort="(params: any) => handleDragSort(group.id, params)" />
            </template>
          </bk-collapse-panel>
        </bk-collapse>
      </template>
    </vuedraggable>

    <!-- 删除确认弹窗 -->
    <bk-dialog
      v-model:is-show="deleteDialogVisible"
      footer-align="center"
      :show-head="false"
      width="480">
      <div class="delete-dialog-content">
        <img
          class="tip-icon"
          src="@images/tip-icon.svg">
        <div class="delete-title">
          {{ t('确定删除该报告？') }}
        </div>
        <div class="delete-warning">
          {{ t('删除的报告将') }}
          <span class="danger-text">{{ t('无法找回') }}</span>
          {{ t('，请谨慎操作！') }}
        </div>
        <div class="delete-confirm-tip">
          {{ t('请输入报表名称') }}
          <span
            v-bk-tooltips="{ content: '点击复制' }"
            class="report-name"
            @click="handleCopyReportName">
            {{ deleteTarget?.bkvisionReport }}
          </span>
          {{ t('以确认删除') }}
        </div>
        <bk-input
          v-model="deleteConfirmInput"
          :placeholder="t('请输入待删除的报表名称')" />
      </div>
      <template #footer>
        <bk-button
          class="mr8"
          :disabled="deleteConfirmInput !== deleteTarget?.bkvisionReport"
          theme="danger"
          @click="handleConfirmDelete">
          {{ t('删除') }}
        </bk-button>
        <bk-button @click="handleCancelDelete">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>

    <!-- 重命名弹窗 -->
    <bk-dialog
      v-model:is-show="renameDialogVisible"
      :title="t('重命名')"
      width="480">
      <bk-form
        ref="renameFormRef"
        form-type="vertical"
        :model="renameFormData"
        :rules="renameFormRules">
        <bk-form-item
          :label="t('分组名称')"
          property="name"
          required>
          <bk-input
            v-model="renameFormData.name"
            :placeholder="t('请输入')" />
        </bk-form-item>
      </bk-form>
      <template #footer>
        <bk-button
          class="mr8"
          :loading="renameLoading"
          theme="primary"
          @click="handleConfirmRename">
          {{ t('确定') }}
        </bk-button>
        <bk-button @click="handleCancelRename">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>

    <!-- 启用/停用确认弹窗 -->
    <bk-dialog
      v-model:is-show="toggleStatusDialogVisible"
      footer-align="center"
      :show-head="false"
      width="400">
      <div class="toggle-status-dialog-content">
        <div class="toggle-status-title">
          {{ toggleStatusTarget?.status === 'enabled' ? t('确认停用该报表？') : t('确认启用该报表？') }}
        </div>
        <div class="toggle-status-tip">
          {{ toggleStatusTarget?.status === 'enabled' ? t('停用后，该报表将从审计报表菜单中隐藏') : t('启用后，该报表将在审计报表菜单中展示') }}
        </div>
      </div>
      <template #footer>
        <bk-button
          class="mr8"
          :loading="toggleStatusLoading"
          :theme="toggleStatusTarget?.status === 'enabled' ? 'danger' : 'primary'"
          @click="handleConfirmToggleStatus">
          {{ toggleStatusTarget?.status === 'enabled' ? t('停用') : t('启用') }}
        </bk-button>
        <bk-button @click="handleCancelToggleStatus">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>
  </div>
</template>

<script setup lang='tsx'>
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import useMessage from '@hooks/use-message';

  import { PrimaryTable } from '@blueking/tdesign-ui';

  export interface Report {
    id: string;
    name: string;
    description: string;
    bkvisionReport: string;
    bkvisionUrl?: string;
    status: 'enabled' | 'disabled';
    updatedBy: string;
    updatedAt: string;
  }

  export interface ReportGroup {
    id: string;
    name: string;
    reports: Report[];
  }

  interface Props {
    groups: ReportGroup[];
    expandAll?: boolean;
  }

  // 拖拽排序结果
  export interface DragSortResult {
    groupId: string;
    currentIndex: number;
    targetIndex: number;
    newOrder: Report[];
  }

  // 分组拖拽排序结果
  export interface GroupDragSortResult {
    newOrder: ReportGroup[];
  }

  interface Emits {
    (e: 'add-report', groupId: string): void;
    (e: 'edit', report: Report): void;
    (e: 'toggle-status', report: Report): void;
    (e: 'delete', report: Report): void;
    (e: 'drag-sort', result: DragSortResult): void;
    (e: 'group-drag-sort', result: GroupDragSortResult): void;
    (e: 'rename-group', groupId: string, newName: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    groups: () => [],
    expandAll: false,
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();

  // 展开的分组
  const activeGroups = ref<string[]>([]);

  // 本地分组数据（用于拖拽排序）
  const localGroups = ref<ReportGroup[]>([]);

  // 删除相关状态
  const deleteDialogVisible = ref(false);
  const deleteTarget = ref<Report | null>(null);
  const deleteConfirmInput = ref('');

  // 重命名相关状态
  const renameDialogVisible = ref(false);
  const renameFormRef = ref();
  const renameLoading = ref(false);
  const renameTarget = ref<ReportGroup | null>(null);
  const renameFormData = ref({
    name: '',
  });
  const renameFormRules = {
    name: [
      {
        required: true,
        message: t('分组名称不能为空'),
        trigger: 'blur',
      },
    ],
  };

  // 启用/停用确认相关状态
  const toggleStatusDialogVisible = ref(false);
  const toggleStatusTarget = ref<Report | null>(null);
  const toggleStatusLoading = ref(false);

  // 同步 props.groups 到 localGroups
  watch(() => props.groups, (groups) => {
    localGroups.value = [...groups];
    if (groups.length > 0 && activeGroups.value.length === 0) {
      activeGroups.value = [groups[0].id];
    }
  }, { immediate: true, deep: true });

  // 表格列定义 (tdesign PrimaryTable 格式)
  const tableColumns = [

    {
      colKey: 'drag', // 列拖拽排序必要参数
      title: '',
      cell: () => (
            <span>
                <audit-icon
                    class="table-drag-icon"
                    type="move" />
            </span>
        ),
      width: 50,
    },

    {
      title: t('报表ID'),
      colKey: 'id',
      width: 120,
      cell: (_h: any, { row }: { row: Report }) => (
            <bk-button text theme="primary">{row.id}</bk-button>
        ),
    },
    {
      title: t('报表名称'),
      colKey: 'name',
      minWidth: 200,
    },
    {
      title: t('描述'),
      colKey: 'description',
      width: 150,
    },
    {
      title: t('BKVision 报表'),
      colKey: 'bkvisionReport',
      minWidth: 200,
      cell: (_h: any, { row }: { row: Report }) => (
            <span class="bkvision-report-cell">
                {row.bkvisionReport}
                        <audit-icon type="jump-link" class="jump-link" />
            </span>
        ),
    },
    {
      title: t('启用状态'),
      colKey: 'status',
      width: 100,
      cell: (_h: any, { row }: { row: Report }) => (
            <bk-tag theme={row.status === 'enabled' ? 'success' : ''}>
                {row.status === 'enabled' ? t('启用') : t('停用')}
            </bk-tag>
        ),
    },
    {
      title: t('更新人'),
      colKey: 'updatedBy',
      width: 150,
    },
    {
      title: t('更新时间'),
      colKey: 'updatedAt',
      width: 180,
      sorter: true,
    },
    {
      title: t('操作'),
      colKey: 'action',
      width: 150,
      cell: (_h: any, { row }: { row: Report }) => (
            <div class="action-column">
                <bk-button
                    text
                    theme="primary"
                    class="mr8"
                    onClick={() => handleEdit(row)}>
                    {t('编辑')}
                </bk-button>
                {row.status === 'enabled' ? (
                    <bk-button
                        text
                        theme="primary"
                        class="mr8"
                        onClick={() => handleShowToggleStatusConfirm(row)}>
                        {t('停用')}
                    </bk-button>
                ) : (
                    <bk-button
                        text
                        theme="primary"
                        class="mr8"
                        onClick={() => handleShowToggleStatusConfirm(row)}>
                        {t('启用')}
                    </bk-button>
                )}
                <bk-dropdown
                    >
                    {{
                        default: () => (
                            <bk-button text theme="primary">
                                <audit-icon type="more" />
                            </bk-button>
                        ),
                        content: () => (
                            <bk-dropdown-menu>
                                <bk-dropdown-item>
                                    <div
                                        class="action-item danger"
                                        onClick={() => handleShowDeleteConfirm(row)}>
                                        {t('删除')}
                                    </div>
                                </bk-dropdown-item>
                            </bk-dropdown-menu>
                        ),
                    }}
                </bk-dropdown>
            </div>
        ),
    },
  ];

  // 监听全部展开/收起
  watch(() => props.expandAll, (val) => {
    if (val) {
      activeGroups.value = localGroups.value.map(group => group.id);
    } else {
      activeGroups.value = [];
    }
  });

  // 在分组中添加报表
  const handleAddReport = (groupId: string) => {
    emit('add-report', groupId);
  };

  // 编辑报表
  const handleEdit = (report: Report) => {
    emit('edit', report);
  };

  // 显示启用/停用确认弹窗
  const handleShowToggleStatusConfirm = (report: Report) => {
    toggleStatusTarget.value = report;
    toggleStatusDialogVisible.value = true;
  };

  // 确认启用/停用
  const handleConfirmToggleStatus = () => {
    if (toggleStatusTarget.value) {
      toggleStatusLoading.value = true;
      emit('toggle-status', toggleStatusTarget.value);
      toggleStatusDialogVisible.value = false;
      toggleStatusTarget.value = null;
      toggleStatusLoading.value = false;
    }
  };

  // 取消启用/停用
  const handleCancelToggleStatus = () => {
    toggleStatusDialogVisible.value = false;
    toggleStatusTarget.value = null;
  };

  // 显示删除确认弹窗
  const handleShowDeleteConfirm = (report: Report) => {
    deleteTarget.value = report;
    deleteConfirmInput.value = '';
    deleteDialogVisible.value = true;
  };

  // 确认删除
  const handleConfirmDelete = () => {
    if (deleteTarget.value && deleteConfirmInput.value === deleteTarget.value.bkvisionReport) {
      console.log('删除报表:', deleteTarget.value);
      emit('delete', deleteTarget.value);
      deleteDialogVisible.value = false;
      deleteTarget.value = null;
      deleteConfirmInput.value = '';
    }
  };

  // 取消删除
  const handleCancelDelete = () => {
    deleteDialogVisible.value = false;
    deleteTarget.value = null;
    deleteConfirmInput.value = '';
  };

  // 复制报表名称到剪贴板
  const handleCopyReportName = () => {
    if (deleteTarget.value?.bkvisionReport) {
      navigator.clipboard.writeText(deleteTarget.value.bkvisionReport)
        .then(() => {
          messageSuccess(t('复制成功'));
        })
        .catch((err) => {
          console.error('复制失败:', err);
        });
    }
  };

  // 显示重命名弹窗
  const handleShowRenameDialog = (group: ReportGroup) => {
    renameTarget.value = group;
    renameFormData.value.name = group.name;
    renameDialogVisible.value = true;
  };

  // 确认重命名
  const handleConfirmRename = async () => {
    try {
      await renameFormRef.value?.validate();
      if (renameTarget.value) {
        renameLoading.value = true;
        emit('rename-group', renameTarget.value.id, renameFormData.value.name);
        renameDialogVisible.value = false;
        renameTarget.value = null;
        renameFormData.value.name = '';
        renameLoading.value = false;
      }
    } catch {
      // 表单验证失败
    }
  };

  // 取消重命名
  const handleCancelRename = () => {
    renameDialogVisible.value = false;
    renameTarget.value = null;
    renameFormData.value.name = '';
  };

  // 处理表格拖拽排序
  const handleDragSort = (groupId: string, params: any) => {
    const { currentIndex, targetIndex, newData } = params;
    // 返回拖拽结果给父组件
    emit('drag-sort', {
      groupId,
      currentIndex,
      targetIndex,
      newOrder: newData as Report[],
    });
  };

  // 处理分组拖拽结束
  const handleGroupDragEnd = () => {
    emit('group-drag-sort', {
      newOrder: localGroups.value,
    });
  };
</script>

<style lang="postcss" scoped>
.report-group-list {
  min-height: 400px;
}

.mr4 {
  margin-right: 4px;
}

.mr8 {
  margin-right: 8px;
}

.ml4 {
  margin-left: 4px;
}

.report-collapse {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-collapse-item {
  :deep(.bk-collapse-item) {
    border-radius: 2px;

    .bk-collapse-header {
      padding: 0;
    }

    .bk-collapse-content {
      padding: 0;
    }
  }
}

.collapse-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: 42px;
  padding: 0 16px;
  cursor: pointer;
  background-color: #f0f1f5;
}

.collapse-header-left {
  display: flex;
  align-items: center;
}

.drag-icon {
  font-size: 18px;
  color: #c4c6cc;
  cursor: grab;

  &:hover {
    color: #979ba5;
  }
}

.group-drag-handle {
  cursor: grab;

  &:active {
    cursor: grabbing;
  }
}

.expand-icon {
  font-size: 12px;
  color: #63656e;
  transition: transform .2s ease;

  &.expanded {
    transform: rotate(0deg);
  }

  &:not(.expanded) {
    transform: rotate(-90deg);
  }
}

.group-name {
  font-size: 14px;
  font-weight: 600;
  color: #313238;
}

.group-count {
  height: 18px;
  min-width: 20px;
  padding: 0 6px;
  margin-left: 8px;
  font-size: 12px;
  line-height: 18px;
  text-align: center;
  background-color: #fff;
  border-radius: 9px;
}

.collapse-header-right {
  display: flex;
  align-items: center;

  .group-more-btn {
    margin-left: 8px;
    color: #979ba5;

    &:hover {
      color: #3a84ff;
    }
  }
}

:deep(.table-drag-icon) {
  font-size: 18px;
  color: #c4c6cc;
  cursor: grab;

  &:hover {
    color: #979ba5;
  }
}

:deep(.t-table) {
  border: none;

  .t-table__header th {
    background: #f5f7fa;
  }

  /* 拖拽行样式 */
  .t-table__row--dragging {
    background: #e1ecff;
    opacity: 80%;
  }
}

/* vuedraggable 拖拽中的样式 */
.sortable-ghost {
  background: #e1ecff;
  opacity: 50%;
}

.sortable-chosen {
  background: #fff;
  box-shadow: 0 2px 8px rgb(0 0 0 / 15%);
}

/* 操作列样式 */
:deep(.action-column) {
  display: flex;
  align-items: center;
}

/* BKVision 报表单元格 */
:deep(.bkvision-report-cell) {
  display: inline-flex;
  align-items: center;

  .jump-link {
    margin-left: 4px;
    font-size: 14px;
    color: #3a84ff;
    cursor: pointer;
    opacity: 0%;
    transition: opacity .2s;

    &:hover {
      color: #699df4;
    }
  }
}

/* 表格行 hover 时显示跳转图标 */
:deep(.t-table__body tr:hover .jump-link) {
  opacity: 100%;
}

/* 更多操作下拉菜单 */
:deep(.action-item) {
  font-size: 12px;
  color: #63656e;
  cursor: pointer;

  &.danger {
    color: #ea3636;
  }
}

/* 删除确认弹窗样式 */
.delete-dialog-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0 8px;

  .tip-icon {
    position: absolute;
    top: -25px;
    left: 50%;
    width: 50px;
    height: 50px;
    margin-bottom: 16px;
    transform: translateX(-50%)
  }

  .delete-title {
    margin-bottom: 24px;
    font-size: 20px;
    color: #313238;
  }

  .delete-warning {
    width: 100%;
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 14px;
    color: #63656e;
    background: #f5f7fa;
    border-radius: 2px;
  }

  .danger-text {
    font-weight: 600;
    color: #ea3636;
  }

  .delete-confirm-tip {
    width: 100%;
    margin-bottom: 8px;
    font-size: 14px;
    color: #63656e;
    text-align: left;
  }

  .report-name {
    color: #3a84ff;
    cursor: pointer;
  }

  .bk-input {
    width: 100%;
  }
}

/* 启用/停用确认弹窗样式 */
.toggle-status-dialog-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
  text-align: center;

  .toggle-status-title {
    margin-bottom: 16px;
    font-size: 20px;
    color: #313238;
  }

  .toggle-status-tip {
    font-size: 14px;
    color: #63656e;
  }
}
</style>
