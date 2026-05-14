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
                  <bk-dropdown
                    :disabled="isPlatformGroup(group)"
                    trigger="hover">
                    <bk-button
                      v-bk-tooltips="{
                        content: t('平台报表为系统内置分组，不支持重命名和删除'),
                        disabled: !isPlatformGroup(group),
                      }"
                      class="group-more-btn ml8"
                      :disabled="isPlatformGroup(group)"
                      text
                      theme="primary">
                      <audit-icon type="more" />
                    </bk-button>
                    <template #content>
                      <bk-dropdown-menu>
                        <bk-dropdown-item>
                          <div
                            class="action-item"
                            @click="handleShowRenameGroup(group)">
                            {{ t('重命名') }}
                          </div>
                        </bk-dropdown-item>
                        <bk-dropdown-item>
                          <div
                            v-bk-tooltips="{
                              content: t('当前分组下还有报表，不支持删除'),
                              disabled: group.reports.length === 0,
                            }"
                            class="action-item danger"
                            :class="{ disableddel: group.reports.length > 0 }"
                            @click="group.reports.length === 0 && handleShowDeleteGroupConfirm(group)">
                            {{ t('删除') }}
                          </div>
                        </bk-dropdown-item>
                      </bk-dropdown-menu>
                    </template>
                  </bk-dropdown>
                </div>
              </div>
            </template>
            <template #content>
              <div class="custom-table">
                <!-- 表头 -->
                <div class="custom-table-header">
                  <div class="custom-table-cell drag-cell" />
                  <div class="custom-table-cell id-cell">
                    {{ t('报表名称') }}
                  </div>

                  <div class="custom-table-cell desc-cell">
                    {{ t('描述') }}
                  </div>
                  <div class="custom-table-cell bkvision-cell">
                    {{ t('BKVision 报表') }}
                  </div>
                  <div class="custom-table-cell status-cell">
                    {{ t('启用状态') }}
                  </div>
                  <div class="custom-table-cell updater-cell">
                    {{ t('更新人') }}
                  </div>
                  <div class="custom-table-cell time-cell">
                    {{ t('更新时间') }}
                  </div>
                  <div class="custom-table-cell action-cell">
                    {{ t('操作') }}
                  </div>
                </div>
                <!-- 表体 - 使用 vuedraggable 支持跨分组拖拽 -->
                <vuedraggable
                  v-model="group.reports"
                  class="custom-table-body"
                  :group="{ name: 'reports' }"
                  handle=".row-drag-handle"
                  item-key="id"
                  @change="(evt: any) => handleReportDragChange(group.id, evt)">
                  <template #item="{ element: report }">
                    <div
                      class="custom-table-row"
                      @mouseenter="hoveredReportId = report.id"
                      @mouseleave="hoveredReportId = null">
                      <div class="custom-table-cell drag-cell">
                        <audit-icon
                          class="row-drag-handle table-drag-icon"
                          type="move" />
                      </div>
                      <div class="custom-table-cell id-cell">
                        <tool-tip-text
                          :data="report.name"
                          :line="1" />
                        <bk-tag
                          v-if="report.binding_type === 'platform_binding'"
                          class="platform-binding-tag">
                          {{ t('平台') }}
                        </bk-tag>
                        <!-- hover整行时显示跳转icon，停用状态不显示 -->
                        <audit-icon
                          v-if="hoveredReportId === report.id && report.status === 'published'"
                          v-bk-tooltips="t('点击查看审计报表')"
                          class="jump-link id-jump-link"
                          type="jump-link"
                          @click.stop="handleGoAuditReport(report)" />
                      </div>
                      <div class="custom-table-cell desc-cell">
                        <tool-tip-text
                          :data="report.description || '-'"
                          :line="1" />
                      </div>
                      <div class="custom-table-cell bkvision-cell">
                        <span
                          v-if="report.bkvisionReportName || report.bkvisionReport"
                          class="bkvision-report-cell">
                          <tool-tip-text
                            :data="report.bkvisionReportName || report.bkvisionReport"
                            :line="1" />
                          <audit-icon
                            v-if="(report.bkvisionReport || report.bkvisionReportName) && hoveredReportId === report.id"
                            v-bk-tooltips="t('跳转至BKVision查看')"
                            class="jump-link"
                            type="jump-link"
                            @click.stop="handleGoBkvision(report)" />
                        </span>
                        <span
                          v-else
                          class="bkvision-report-cell">
                          <span class="cell-text">-</span>
                        </span>
                      </div>
                      <div class="custom-table-cell status-cell">
                        <bk-tag :theme="report.status === 'published' ? 'success' : ''">
                          {{ report.status === 'published' ? t('启用') : t('停用') }}
                        </bk-tag>
                      </div>
                      <div class="custom-table-cell updater-cell">
                        <span class="cell-text">{{ report.updatedBy }}</span>
                      </div>
                      <div class="custom-table-cell time-cell">
                        <span class="time-text">{{ formatUpdateTime(report.updatedAt) }}</span>
                      </div>
                      <div class="custom-table-cell action-cell">
                        <div class="action-column">
                          <bk-button
                            v-bk-tooltips="{
                              content: t('平台报表不支持编辑'),
                              disabled: report.binding_type !== 'platform_binding',
                            }"
                            class="mr8"
                            :disabled="report.binding_type === 'platform_binding'"
                            text
                            theme="primary"
                            @click="handleEdit(report)">
                            {{ t('编辑') }}
                          </bk-button>
                          <bk-button
                            class="mr8"
                            text
                            theme="primary"
                            @click="handleShowMoveToGroup(report, group.id)">
                            {{ t('移动到分组') }}
                          </bk-button>
                          <bk-dropdown
                            trigger="hover">
                            <bk-button
                              text
                              theme="primary">
                              <audit-icon type="more" />
                            </bk-button>
                            <template #content>
                              <bk-dropdown-menu>
                                <bk-dropdown-item>
                                  <div
                                    v-bk-tooltips="{
                                      content: t('平台绑定的报表不支持停用操作'),
                                      disabled: report.binding_type !== 'platform_binding',
                                    }"
                                    class="action-item"
                                    :class="{ disableddel: report.binding_type === 'platform_binding' }"
                                    @click="report.binding_type !== 'platform_binding'
                                      && handleShowToggleStatusConfirm(report)">
                                    {{ report.status === 'published' ? t('停用') : t('启用') }}
                                  </div>
                                </bk-dropdown-item>
                                <bk-dropdown-item>
                                  <div
                                    v-bk-tooltips="{
                                      content: t('请先停用后再删除'),
                                      disabled: report.status !== 'published'
                                    }"
                                    class="action-item danger"
                                    :class="{ disableddel: report.status === 'published' }"
                                    @click="report.status !== 'published' && handleShowDeleteConfirm(report)">
                                    {{ t('删除') }}
                                  </div>
                                </bk-dropdown-item>
                              </bk-dropdown-menu>
                            </template>
                          </bk-dropdown>
                        </div>
                      </div>
                    </div>
                  </template>
                </vuedraggable>
                <!-- 空状态 -->
                <div
                  v-if="group.reports.length === 0"
                  class="custom-table-empty">
                  {{ t('暂无数据') }}
                </div>
              </div>
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
            {{ deleteTarget?.name }}
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
          :disabled="deleteConfirmInput !== deleteTarget?.name"
          :loading="deleteLoading"
          theme="danger"
          @click="handleConfirmDelete">
          {{ t('删除') }}
        </bk-button>
        <bk-button @click="handleCancelDelete">
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
          {{ toggleStatusTarget?.status === 'published' ? t('确认停用该报表？') : t('确认启用该报表？') }}
        </div>
        <div class="toggle-status-tip">
          {{ toggleStatusTarget?.status === 'published' ? t('停用后，该报表将从审计报表菜单中隐藏') : t('启用后，该报表将在审计报表菜单中展示') }}
        </div>
      </div>
      <template #footer>
        <bk-button
          class="mr8"
          :loading="toggleStatusLoading"
          :theme="toggleStatusTarget?.status === 'published' ? 'danger' : 'primary'"
          @click="handleConfirmToggleStatus">
          {{ toggleStatusTarget?.status === 'published' ? t('停用') : t('启用') }}
        </bk-button>
        <bk-button @click="handleCancelToggleStatus">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>

    <!-- 移动到分组弹窗 -->
    <bk-dialog
      v-model:is-show="moveToGroupDialogVisible"
      :title="t('移动到分组')"
      width="480">
      <bk-form form-type="vertical">
        <bk-form-item
          :label="t('目标分组')"
          required>
          <bk-select
            v-model="moveToGroupTargetId"
            :clearable="false"
            :placeholder="t('请选择')">
            <bk-option
              v-for="group in localGroups.filter(g => g.id !== moveToGroupSourceId)"
              :id="group.id"
              :key="group.id"
              :name="group.name" />
          </bk-select>
        </bk-form-item>
      </bk-form>
      <template #footer>
        <bk-button
          class="mr8"
          :disabled="!moveToGroupTargetId"
          theme="primary"
          @click="handleConfirmMoveToGroup">
          {{ t('确定') }}
        </bk-button>
        <bk-button @click="handleCancelMoveToGroup">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>

    <!-- 重命名分组弹窗 -->
    <bk-dialog
      v-model:is-show="renameGroupDialogVisible"
      :title="t('重命名')"
      width="480">
      <bk-form
        ref="renameGroupFormRef"
        form-type="vertical"
        :model="renameGroupFormData"
        :rules="renameGroupFormRules">
        <bk-form-item
          :label="t('分组名称')"
          property="name"
          required>
          <bk-input
            v-model="renameGroupFormData.name"
            :placeholder="t('请输入')" />
        </bk-form-item>
      </bk-form>
      <template #footer>
        <bk-button
          class="mr8"
          :loading="renameGroupLoading"
          theme="primary"
          @click="handleConfirmRenameGroup">
          {{ t('确定') }}
        </bk-button>
        <bk-button @click="handleCancelRenameGroup">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>

    <!-- 删除分组确认弹窗 -->
    <bk-dialog
      v-model:is-show="deleteGroupDialogVisible"
      footer-align="center"
      :show-head="false"
      width="400">
      <div class="toggle-status-dialog-content">
        <div class="toggle-status-title">
          {{ t('是否删除该分组？') }}
        </div>
        <div class="delete-group-info">
          {{ t('分组：') }}<span class="group-name-highlight">{{ deleteGroupTarget?.name }}</span>
        </div>
      </div>
      <template #footer>
        <bk-button
          class="mr8"
          :loading="deleteGroupLoading"
          theme="danger"
          @click="handleConfirmDeleteGroup">
          {{ t('删除') }}
        </bk-button>
        <bk-button @click="handleCancelDeleteGroup">
          {{ t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>
  </div>
</template>

<script setup lang='tsx'>
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';
  import Vuedraggable from 'vuedraggable';

  import ReportConfigService from '@service/report-config';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  export interface Report {
    id: string;
    name: string;
    description: string;
    binding_type: string;
    vision_id: string;
    bkvisionReport?: string;
    bkvisionReportName?: string;
    bkvisionSpaceUid?: string;
    status: 'published' | 'unpublished';
    updatedBy: string;
    updatedAt: string;
  }

  export interface ReportGroup {
    id: number;
    name: string;
    group_type?: string;
    reports: Report[];
    priority_index: number;
  }

  interface Props {
    groups: ReportGroup[];
    activeGroups?: number[];
  }

  // 拖拽排序结果
  export interface DragSortResult {
    groupId: number;
    currentIndex: number;
    targetIndex: number;
    newOrder: Report[];
  }

  // 分组拖拽排序结果
  export interface GroupDragSortResult {
    newOrder: ReportGroup[];
  }

  // 跨分组拖拽结果
  export interface CrossGroupDragResult {
    reportId: string;
    fromGroupId: number;
    toGroupId: number;
    newIndex: number;
  }

  interface Emits {
    (e: 'add-report', groupId: number): void;
    (e: 'edit', report: Report): void;
    (e: 'toggle-status', report: Report): void;
    (e: 'status-updated'): void;
    (e: 'delete', report: Report): void;
    (e: 'deleted'): void;
    (e: 'drag-sort', result: DragSortResult): void;
    (e: 'group-drag-sort', result: GroupDragSortResult): void;
    (e: 'order-updated'): void;
    (e: 'update:activeGroups', value: number[]): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    groups: () => [],
    activeGroups: () => [],
  });

  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const router = useRouter();
  const { messageSuccess } = useMessage();

  // 格式化更新时间：将 T 替换为空格，去掉毫秒，时区用空格分隔
  // 例: "2026-04-08T11:37:31.736326+08:00" → "2026-04-08 11:37:31 08:00"
  const formatUpdateTime = (timeStr: string): string => {
    if (!timeStr) return '-';
    return timeStr
      .replace('T', ' ')        // 替换 T 为空格
      .replace(/\.\d{6}/, '')    // 移除毫秒部分
      .replace(/\+/, ' ');       // 时区 + 号替换为空格
  };

  // 展开的分组（内部管理，用持久备份防止 bk-collapse 重置）
  // eslint-disable-next-line vue/no-dupe-keys
  const activeGroups = ref<number[]>([]);
  // 持久化备份：用户操作展开/收起时保存，数据刷新时恢复
  const savedActiveGroups = ref<number[]>([]);
  // 标记是否已完成首次初始化
  let isInitialized = false;

  // 当前 hover 的报表行 ID
  const hoveredReportId = ref<string | null>(null);

  // 判断是否为平台报表分组（系统内置分组）
  const isPlatformGroup = (group: ReportGroup): boolean => group.group_type === 'platform';

  // 本地分组数据（用于拖拽排序）
  const localGroups = ref<ReportGroup[]>([]);

  // 删除相关状态
  const deleteDialogVisible = ref(false);
  const deleteTarget = ref<Report | null>(null);
  const deleteConfirmInput = ref('');

  // 启用/停用确认相关状态
  const toggleStatusDialogVisible = ref(false);
  const toggleStatusTarget = ref<Report | null>(null);

  // 移动到分组相关状态
  const moveToGroupDialogVisible = ref(false);
  const moveToGroupTarget = ref<Report | null>(null);
  const moveToGroupSourceId = ref<number | null>(null);
  const moveToGroupTargetId = ref<number | null>(null);

  // 用于跟踪报表原始所属分组
  const reportGroupMap = ref<Map<string, number>>(new Map());

  // 重命名分组相关状态
  const renameGroupDialogVisible = ref(false);
  const renameGroupFormRef = ref();
  const renameGroupTarget = ref<ReportGroup | null>(null);
  const renameGroupFormData = ref({ name: '' });
  const renameGroupFormRules = {
    name: [
      {
        required: true,
        message: t('分组名称不能为空'),
        trigger: 'blur',
      },
    ],
  };

  // 删除分组相关状态
  const deleteGroupDialogVisible = ref(false);
  const deleteGroupTarget = ref<ReportGroup | null>(null);

  // 更新报表-分组映射
  const updateReportGroupMap = () => {
    reportGroupMap.value.clear();
    localGroups.value.forEach((group) => {
      group.reports.forEach((report) => {
        reportGroupMap.value.set(report.id, group.id);
      });
    });
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

  // 跳转到审计报表查看页
  const handleGoAuditReport = (report: Report) => {
    const routeData = router.resolve({
      name: 'statementManageDetail',
      params: { id: report.id },
      query: {
        scene_id: getSceneSystemParams().scope_id,
        scene_type: 'scene',
      },
    });
    window.open(routeData.href, '_blank');
  };

  // 跳转到BKVision（参考新建报表预览逻辑）
  const handleGoBkvision = async (report: Report) => {
    const res = await fetchReportDetail({ share_uid: report.vision_id });
    const baseUrl = configData.value.third_party_system?.bkvision_web_url || '';
    window.open(`${baseUrl}#/${report.bkvisionSpaceUid}/dashboards/detail/root/${res.data.dashboard_uid}`);
  };
  // 调用排序接口
  const {
    run: orderPanels,
  } = useRequest(ReportConfigService.orderPanels, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('排序成功'));
      emit('order-updated'); // 通知父组件刷新列表
    },
  });

  // 构建排序参数 - 收集指定分组的所有 Panel
  const buildOrderParams = (groupId: number) => {
    const items: Array<{ panel_id: string; group_id: number; priority_index: number }> = [];
    const group = localGroups.value.find(g => g.id === groupId);

    if (group) {
      // priority_index 按显示顺序从大到小赋值
      const totalReports = group.reports.length;
      group.reports.forEach((report, index) => {
        items.push({
          panel_id: report.id,
          group_id: groupId, // 所有报表的 group_id 都设为目标分组 ID
          priority_index: totalReports - 1 - index, // 第一个显示的 priority_index 最大
        });
      });
    }

    return {
      scene_id: getSceneSystemParams().scope_id,
      items,
    };
  };

  // 处理报表拖拽变化（包括跨分组拖拽）
  const handleReportDragChange = (targetGroupId: number, evt: any) => {
    // 添加事件 - 从其他分组拖入（跨分组拖拽）
    if (evt.added) {
      const { element: report } = evt.added;
      // 跨分组拖拽 - 只传目标分组（B分组）的所有数据
      const params = buildOrderParams(targetGroupId);
      orderPanels(params);
      // 更新映射
      reportGroupMap.value.set(report.id, targetGroupId);
    }

    // 移动事件 - 同分组内排序
    if (evt.moved) {
      const { oldIndex, newIndex } = evt.moved;
      const group = localGroups.value.find(g => g.id === targetGroupId);

      if (group) {
        // 调用排序接口 - 只传当前分组的数据
        const params = buildOrderParams(targetGroupId);
        orderPanels(params);

        // 通知父组件（用于 UI 更新）
        emit('drag-sort', {
          groupId: targetGroupId,
          currentIndex: oldIndex,
          targetIndex: newIndex,
          newOrder: group.reports,
        });
      }
    }
  };

  // 在分组中添加报表
  const handleAddReport = (groupId: number) => {
    emit('add-report', groupId);
  };

  // 编辑报表
  const handleEdit = (report: Report) => {
    emit('edit', report);
  };

  // 显示移动到分组弹窗
  const handleShowMoveToGroup = (report: Report, currentGroupId: number) => {
    moveToGroupTarget.value = report;
    moveToGroupSourceId.value = currentGroupId;
    moveToGroupTargetId.value = null;
    moveToGroupDialogVisible.value = true;
  };

  // 确认移动到分组
  const handleConfirmMoveToGroup = () => {
    if (moveToGroupTarget.value && moveToGroupTargetId.value && moveToGroupSourceId.value) {
      // 从源分组移除报表
      const sourceGroup = localGroups.value.find(g => g.id === moveToGroupSourceId.value);
      const targetGroup = localGroups.value.find(g => g.id === moveToGroupTargetId.value);

      if (sourceGroup && targetGroup) {
        const reportIndex = sourceGroup.reports.findIndex(r => r.id === moveToGroupTarget.value!.id);
        if (reportIndex > -1) {
          const [report] = sourceGroup.reports.splice(reportIndex, 1);
          targetGroup.reports.push(report);

          // 调用排序接口更新目标分组
          const params = buildOrderParams(moveToGroupTargetId.value);
          orderPanels(params);

          // 更新映射
          reportGroupMap.value.set(report.id, moveToGroupTargetId.value);
        }
      }
    }
    moveToGroupDialogVisible.value = false;
    moveToGroupTarget.value = null;
    moveToGroupSourceId.value = null;
    moveToGroupTargetId.value = null;
  };

  // 取消移动到分组
  const handleCancelMoveToGroup = () => {
    moveToGroupDialogVisible.value = false;
    moveToGroupTarget.value = null;
    moveToGroupSourceId.value = null;
    moveToGroupTargetId.value = null;
  };

  // 显示启用/停用确认弹窗
  const handleShowToggleStatusConfirm = (report: Report) => {
    toggleStatusTarget.value = report;
    toggleStatusDialogVisible.value = true;
  };

  // 更新 Panel 状态
  const {
    run: updatePanelStatus,
    loading: toggleStatusLoading,
  } = useRequest(ReportConfigService.updatePanel, {
    defaultValue: null,
    onSuccess: () => {
      const isEnabling = toggleStatusTarget.value?.status === 'unpublished';
      messageSuccess(isEnabling ? t('启用成功') : t('停用成功'));
      toggleStatusDialogVisible.value = false;
      toggleStatusTarget.value = null;
      emit('status-updated'); // 通知父组件刷新列表
    },
  });

  // 确认启用/停用
  const handleConfirmToggleStatus = () => {
    if (toggleStatusTarget.value) {
      // 查找报表所属分组
      const group = localGroups.value.find(g => g.reports.some(r => r.id === toggleStatusTarget.value!.id));
      const groupId = group?.id ?? 0;
      const isEnabling = toggleStatusTarget.value.status !== 'published';
      updatePanelStatus({
        id: toggleStatusTarget.value.id,
        scene_id: getSceneSystemParams().scope_id,
        group_id: groupId,
        panel_id: toggleStatusTarget.value.id,
        name: toggleStatusTarget.value.name,
        status: isEnabling ? 'published' : 'unpublished',
      });
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

  // 删除 Panel
  const {
    run: deletePanel,
    loading: deleteLoading,
  } = useRequest(ReportConfigService.deletePanel, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('删除成功'));
      deleteDialogVisible.value = false;
      deleteTarget.value = null;
      deleteConfirmInput.value = '';
      emit('deleted'); // 通知父组件刷新列表
    },
  });

  // 确认删除
  const handleConfirmDelete = () => {
    if (deleteTarget.value && deleteConfirmInput.value === deleteTarget.value.name) {
      deletePanel({ id: deleteTarget.value.id, scene_id: getSceneSystemParams().scope_id });
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
    if (deleteTarget.value?.name) {
      navigator.clipboard.writeText(deleteTarget.value.name)
        .then(() => {
          messageSuccess(t('复制成功'));
        })
        .catch((err) => {
          console.error('复制失败:', err);
        });
    }
  };

  // 调用分组排序接口
  const {
    run: orderGroups,
  } = useRequest(ReportConfigService.orderGroups, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('排序成功'));
      emit('order-updated'); // 通知父组件刷新列表
    },
  });

  // 构建分组排序参数
  const buildGroupOrderParams = () => {
    const totalGroups = localGroups.value.length;
    const groups = localGroups.value.map((group, index) => ({
      group_id: group.id,
      priority_index: totalGroups - 1 - index,
    }));
    return {
      scene_id: getSceneSystemParams().scope_id,
      groups,
    };
  };

  // 处理分组拖拽结束
  const handleGroupDragEnd = () => {
    // 调用分组排序接口
    const params = buildGroupOrderParams();
    orderGroups(params);

    // 通知父组件（用于 UI 更新）
    emit('group-drag-sort', {
      newOrder: localGroups.value,
    });
  };

  // 显示重命名分组弹窗
  const handleShowRenameGroup = (group: ReportGroup) => {
    renameGroupTarget.value = group;
    renameGroupFormData.value.name = group.name;
    renameGroupDialogVisible.value = true;
  };

  // 更新分组（重命名）
  const {
    run: updateGroup,
    loading: renameGroupLoading,
  } = useRequest(ReportConfigService.updateGroup, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('重命名成功'));
      renameGroupDialogVisible.value = false;
      renameGroupTarget.value = null;
      renameGroupFormData.value.name = '';
      emit('order-updated'); // 通知父组件刷新列表
    },
  });

  // 确认重命名分组
  const handleConfirmRenameGroup = async () => {
    try {
      await renameGroupFormRef.value?.validate();
      if (renameGroupTarget.value) {
        updateGroup({
          scene_id: getSceneSystemParams().scope_id,
          group_id: renameGroupTarget.value.id,
          name: renameGroupFormData.value.name,
          priority_index: renameGroupTarget.value.priority_index,
        });
      }
    } catch {
      // 表单验证失败
    }
  };

  // 取消重命名分组
  const handleCancelRenameGroup = () => {
    renameGroupDialogVisible.value = false;
    renameGroupTarget.value = null;
    renameGroupFormData.value.name = '';
  };

  // 显示删除分组确认弹窗
  const handleShowDeleteGroupConfirm = (group: ReportGroup) => {
    deleteGroupTarget.value = group;
    deleteGroupDialogVisible.value = true;
  };

  // 删除分组
  const {
    run: deleteGroup,
    loading: deleteGroupLoading,
  } = useRequest(ReportConfigService.deleteGroup, {
    defaultValue: null,
    onSuccess: () => {
      messageSuccess(t('删除成功'));
      deleteGroupDialogVisible.value = false;
      deleteGroupTarget.value = null;
      emit('order-updated'); // 通知父组件刷新列表
    },
  });

  // 确认删除分组
  const handleConfirmDeleteGroup = () => {
    if (deleteGroupTarget.value) {
      deleteGroup({ id: deleteGroupTarget.value.id, scene_id: getSceneSystemParams().scope_id });
    }
  };

  // 取消删除分组
  const handleCancelDeleteGroup = () => {
    deleteGroupDialogVisible.value = false;
    deleteGroupTarget.value = null;
  };

  // 同步 props.groups 到 localGroups
  watch(() => props.groups, (groups) => {
    localGroups.value = [...groups];
    // 有数据时恢复展开状态
    if (groups.length > 0) {
      if (savedActiveGroups.value.length > 0) {
        // 从持久备份恢复（清理已删除/不存在的分组）
        const validIds = new Set(groups.map(g => g.id));
        const restored = savedActiveGroups.value.filter(id => validIds.has(id));
        // 切换场景后旧ID全部失效时，回退到展开第一个
        activeGroups.value = restored.length > 0 ? restored : [groups[0].id];
        // 同步更新持久备份（场景切换后应使用新数据）
        if (restored.length === 0) {
          savedActiveGroups.value = [groups[0].id];
        }
      } else {
        // 首次加载，默认展开第一个（即使 expandAll 为 true 也只展开第一个）
        activeGroups.value = [groups[0].id];
        savedActiveGroups.value = [groups[0].id];
      }
      // 标记首次初始化完成
      if (!isInitialized) {
        isInitialized = true;
      }
    }
  }, { immediate: true, deep: true });

  // 用户操作展开/收起时，同步到持久备份并通知父组件
  watch(activeGroups, (val) => {
    savedActiveGroups.value = [...val];
    emit('update:activeGroups', [...val]);
  }, { deep: true });

  // 监听 props.groups 变化时更新映射
  watch(() => props.groups, () => {
    updateReportGroupMap();
  }, { immediate: true, deep: true });
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

/* 自定义表格样式 */
.custom-table {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #dcdee5;
  border-top: none;

  &::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background-color: #c4c6cc;
    border-radius: 3px;

    &:hover {
      background-color: #979ba5;
    }
  }

  &::-webkit-scrollbar-track {
    background-color: transparent;
  }
}

.custom-table-header {
  display: flex;
  align-items: center;
  height: 42px;
  font-size: 12px;
  color: #313238;
  background-color: #f5f7fa;
  border-bottom: 1px solid #dcdee5;

  .custom-table-cell {
    background-color: #f5f7fa;
  }
}

.custom-table-body {
  min-height: 42px;
}

.custom-table-row {
  display: flex;
  align-items: center;
  min-height: 42px;
  font-size: 12px;
  color: #63656e;
  background-color: #fff;
  border-bottom: 1px solid #dcdee5;
  transition: background-color .2s;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background-color: #f5f7fa;

    .jump-link {
      opacity: 100%;
    }
  }
}

.custom-table-cell {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  height: 100%;
  padding: 0 16px;
  overflow: hidden;
  background-color: inherit;
}

.cell-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 各列宽度定义 */
.drag-cell {
  width: 50px;
  justify-content: center;
  padding: 0;
}

.id-cell {
  position: relative;
  flex: 1;
  min-width: 150px;

}

.id-jump-link {
  flex-shrink: 0;
  margin-left: 4px;
  font-size: 14px;
  color: #3a84ff;
  cursor: pointer;

  &:hover {
    color: #699df4;
  }
}


.desc-cell {
  flex: 1;
  min-width: 120px;
}

.bkvision-cell {
  width: 280px;
}

.status-cell {
  width: 100px;
}

.updater-cell {
  width: 120px;
}

.time-cell {
  min-width: 200px;
}

/* 更新时间列 - 完整展示，不截断 */
.time-text {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.action-cell {
  width: 200px;
}

/* 空状态 */
.custom-table-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  font-size: 14px;
  color: #c4c6cc;
  background-color: #fff;
}

/* 拖拽手柄 */
.row-drag-handle {
  cursor: grab;

  &:active {
    cursor: grabbing;
  }
}

.table-drag-icon {
  font-size: 18px;
  color: #c4c6cc;
  cursor: grab;

  &:hover {
    color: #979ba5;
  }
}

/* vuedraggable 拖拽中的样式 */
.sortable-ghost {
  background: #e1ecff !important;
  opacity: 50%;
}

.sortable-chosen {
  background: #fff !important;
  box-shadow: 0 2px 8px rgb(0 0 0 / 15%);
}

.sortable-drag {
  background: #fff !important;
  box-shadow: 0 4px 12px rgb(0 0 0 / 15%);
}

/* 操作列样式 */
.action-column {
  display: flex;
  align-items: center;
}

/* BKVision 报表单元格 */
.bkvision-report-cell {
  display: inline-flex;
  align-items: center;
  overflow: hidden;

  .cell-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .jump-link {
    flex-shrink: 0;
    margin-left: 4px;
    font-size: 14px;
    color: #3a84ff;
    cursor: pointer;
    opacity: 0%;
    transition: opacity .2s;

    &:hover {
      color: #699df4;
    }

    &.disabled {
      color: #c4c6cc;
      cursor: not-allowed;

      &:hover {
        color: #c4c6cc;
      }
    }
  }
}

/* 更多操作下拉菜单 */
:deep(.action-item) {
  font-size: 12px;
  color: #63656e;
  cursor: pointer;
}

.disableddel {
  color: #c4c6cc;
  cursor: not-allowed;
}

/* 删除确认弹窗样式 */
.delete-dialog-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 50px 0 8px;

  .tip-icon {
    position: absolute;
    top: 5px;
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

/* 删除分组确认弹窗样式 */
.delete-group-info {
  font-size: 14px;
  color: #63656e;
}

.group-name-highlight {
  font-weight: 600;
  color: #313238;
}

.platform-binding-tag {
  margin-left: 5px;
}
</style>
