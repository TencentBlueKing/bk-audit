<template>
  <div
    class="chat-sidebar"
    :class="{ 'is-collapsed': collapsed }">
    <template v-if="!collapsed">
      <!-- 搜索框 -->
      <div class="sidebar-search">
        <div class="search-box">
          <input
            ref="searchInputRef"
            v-model="searchKeyword"
            class="search-input"
            placeholder="搜索对话"
            type="search">
          <search class="search-icon" />
        </div>
        <bk-dropdown
          :is-show="isDropdownShow"
          placement="bottom-end"
          trigger="click"
          @hide="isDropdownShow = false"
          @show="isDropdownShow = true">
          <div
            class="filter-btn"
            :class="{ 'is-active': isDropdownShow }">
            <audit-icon
              class="icon-control"
              type="filter" />
          </div>
          <template #content>
            <bk-dropdown-menu>
              <bk-dropdown-item ext-cls="sub-menu-item">
                <bk-dropdown
                  placement="right-start"
                  style="width: 100%"
                  trigger="hover">
                  <div class="dropdown-sub-trigger">
                    <span>导出对话</span>
                    <angle-right class="sub-icon" />
                  </div>
                  <template #content>
                    <bk-dropdown-menu>
                      <bk-dropdown-item @click="showExportDialog('json')">
                        导出 JSON
                      </bk-dropdown-item>
                      <bk-dropdown-item @click="showExportDialog('markdown')">
                        导出 Markdown
                      </bk-dropdown-item>
                      <bk-dropdown-item @click="showExportDialog('pdf')">
                        导出 PDF
                      </bk-dropdown-item>
                    </bk-dropdown-menu>
                  </template>
                </bk-dropdown>
              </bk-dropdown-item>
              <bk-dropdown-item @click="showImportDialog">
                导入对话
              </bk-dropdown-item>
              <bk-dropdown-item @click="showReportList">
                报告列表
              </bk-dropdown-item>
              <bk-dropdown-item @click="showClearAllDialog">
                清空所有对话
              </bk-dropdown-item>
            </bk-dropdown-menu>
          </template>
        </bk-dropdown>
      </div>

      <!-- 新对话按钮 -->
      <div class="new-chat-area">
        <div
          class="new-chat-btn"
          @click="$emit('new-chat')">
          <span>
            <audit-icon type="add" />
          </span>
          新对话
        </div>
      </div>

      <!-- 对话列表 -->
      <div class="conversation-list">
        <!-- 置顶 -->
        <div
          v-if="filteredPinned.length"
          class="conv-section">
          <div class="section-label">
            置顶
          </div>
          <div
            v-for="conv in filteredPinned"
            :key="conv.id"
            class="conv-item"
            :class="{ 'is-active': activeId === conv.id, 'is-menu-open': activeMenuId === conv.id }"
            @click="$emit('select', conv.id)">
            <span class="conv-dot">•</span>
            <template v-if="editingConvId === conv.id">
              <bk-input
                ref="editConvInputRef"
                v-model="editConvTitle"
                class="conv-title-input"
                size="small"
                @blur="cancelEditConv"
                @click.stop
                @enter="confirmEditConv(conv.id)" />
            </template>
            <template v-else>
              <span class="conv-title">{{ conv.title }}</span>
            </template>
            <div class="conv-actions is-pinned-actions">
              <audit-icon
                class="action-btn pin-icon"
                type="attention" />
              <bk-dropdown
                class="more-dropdown"
                :is-show="activeMenuId === conv.id"
                placement="bottom-end"
                trigger="click"
                @click.stop
                @hide="hideMenu"
                @show="showMenu(conv.id)">
                <ellipsis
                  class="action-btn more-icon"
                  :class="{ 'is-active': activeMenuId === conv.id }" />
                <template #content>
                  <bk-dropdown-menu>
                    <bk-dropdown-item @click="handlePin(conv.id)">
                      取消置顶
                    </bk-dropdown-item>
                    <bk-dropdown-item @click="startEditConv(conv.id, conv.title)">
                      重命名
                    </bk-dropdown-item>
                    <bk-dropdown-item ext-cls="sub-menu-item">
                      <bk-dropdown
                        placement="right-start"
                        style="width: 100%"
                        trigger="hover">
                        <div class="dropdown-sub-trigger">
                          <span>移动到分组</span>
                          <angle-right class="sub-icon" />
                        </div>
                        <template #content>
                          <bk-dropdown-menu>
                            <bk-dropdown-item
                              v-for="g in groups"
                              :key="g.id"
                              @click="moveToGroup(conv.id, g.name)">
                              {{ g.name }}
                            </bk-dropdown-item>
                          </bk-dropdown-menu>
                        </template>
                      </bk-dropdown>
                    </bk-dropdown-item>
                    <bk-dropdown-item ext-cls="sub-menu-item">
                      <bk-dropdown
                        placement="right-start"
                        style="width: 100%"
                        trigger="hover">
                        <div class="dropdown-sub-trigger">
                          <span>导出</span>
                          <angle-right class="sub-icon" />
                        </div>
                        <template #content>
                          <bk-dropdown-menu>
                            <bk-dropdown-item @click="showExportDialog('json')">
                              导出 JSON
                            </bk-dropdown-item>
                            <bk-dropdown-item @click="showExportDialog('markdown')">
                              导出 Markdown
                            </bk-dropdown-item>
                            <bk-dropdown-item @click="showExportDialog('pdf')">
                              导出 PDF
                            </bk-dropdown-item>
                          </bk-dropdown-menu>
                        </template>
                      </bk-dropdown>
                    </bk-dropdown-item>
                    <bk-dropdown-item @click="handleDelete(conv.id)">
                      删除
                    </bk-dropdown-item>
                  </bk-dropdown-menu>
                </template>
              </bk-dropdown>
            </div>
          </div>
        </div>

        <!-- 历史对话（无分组） -->
        <div class="conv-section">
          <div class="section-label">
            <span class="label-text">历史对话</span>
            <span
              class="label-action"
              @click="showAddGroupDialog">
              <plus />
            </span>
          </div>

          <div
            v-for="conv in filteredUngroupedHistory"
            :key="conv.id"
            class="conv-item"
            :class="{ 'is-active': activeId === conv.id, 'is-menu-open': activeMenuId === conv.id }"
            draggable="true"
            @click="$emit('select', conv.id)"
            @dragend="handleDragEnd"
            @dragstart="handleDragStart($event, 'conversation', conv.id)">
            <span class="conv-dot">•</span>
            <template v-if="editingConvId === conv.id">
              <bk-input
                ref="editConvInputRef"
                v-model="editConvTitle"
                class="conv-title-input"
                size="small"
                @blur="cancelEditConv"
                @click.stop
                @enter="confirmEditConv(conv.id)" />
            </template>
            <template v-else>
              <span class="conv-title">{{ conv.title }}</span>
            </template>
            <div class="conv-actions">
              <bk-dropdown
                :is-show="activeMenuId === conv.id"
                placement="bottom-end"
                trigger="click"
                @click.stop
                @hide="hideMenu"
                @show="showMenu(conv.id)">
                <ellipsis
                  class="action-btn"
                  :class="{ 'is-active': activeMenuId === conv.id }" />
                <template #content>
                  <bk-dropdown-menu>
                    <bk-dropdown-item @click="handlePin(conv.id)">
                      置顶对话
                    </bk-dropdown-item>
                    <bk-dropdown-item @click="startEditConv(conv.id, conv.title)">
                      重命名
                    </bk-dropdown-item>
                    <bk-dropdown-item @click="moveToGroup(conv.id, undefined)">
                      移出分组
                    </bk-dropdown-item>
                    <bk-dropdown-item ext-cls="sub-menu-item">
                      <bk-dropdown
                        placement="right-start"
                        style="width: 100%"
                        trigger="hover">
                        <div class="dropdown-sub-trigger">
                          <span>移动到分组</span>
                          <angle-right class="sub-icon" />
                        </div>
                        <template #content>
                          <bk-dropdown-menu>
                            <bk-dropdown-item
                              v-for="g in groups"
                              :key="g.id"
                              @click="moveToGroup(conv.id, g.name)">
                              {{ g.name }}
                            </bk-dropdown-item>
                          </bk-dropdown-menu>
                        </template>
                      </bk-dropdown>
                    </bk-dropdown-item>
                    <bk-dropdown-item @click="handleDelete(conv.id)">
                      删除对话
                    </bk-dropdown-item>
                  </bk-dropdown-menu>
                </template>
              </bk-dropdown>
            </div>
          </div>
        </div>

        <!-- 分组对话 -->
        <div class="conv-section">
          <div
            v-for="group in groups"
            :key="group.id"
            class="group-item"
            :class="getGroupItemDragClass(group.name)"
            draggable="true"
            @dragend="handleDragEnd"
            @dragleave="handleDragLeave"
            @dragover="handleDragOver($event, 'group', group.name)"
            @dragstart="handleDragStart($event, 'group', group.name)"
            @drop="handleDrop($event, 'group', group.name)">
            <div
              class="group-header"
              :class="[
                getGroupHeaderDragClass(group.name),
                { 'is-menu-open': activeGroupMenuId === group.name },
              ]"
              @click="toggleGroup(group.name)">
              <folder
                v-if="collapsedGroups.has(group.name)"
                class="group-icon" />
              <folder-shape
                v-else
                class="group-icon" />

              <template v-if="editingGroup === group.name">
                <bk-input
                  ref="editGroupInputRef"
                  v-model="editGroupName"
                  size="small"
                  @blur="cancelEditGroup"
                  @click.stop
                  @enter="confirmEditGroup(group.name)" />
              </template>
              <template v-else>
                <span class="group-name">{{ group.name }}</span>
                <span class="group-count">{{ filteredGroupedHistory[group.name]?.length || 0 }}</span>
                <bk-dropdown
                  class="group-more-dropdown"
                  :is-show="activeGroupMenuId === group.name"
                  placement="bottom-end"
                  trigger="click"
                  @click.stop
                  @hide="hideGroupMenu"
                  @show="showGroupMenu(group.name)">
                  <ellipsis
                    class="group-more"
                    :class="{ 'is-active': activeGroupMenuId === group.name }" />
                  <template #content>
                    <bk-dropdown-menu>
                      <bk-dropdown-item @click="startEditGroup(group.name)">
                        重命名
                      </bk-dropdown-item>
                      <bk-dropdown-item @click="showDeleteGroup(group.name)">
                        删除分组
                      </bk-dropdown-item>
                    </bk-dropdown-menu>
                  </template>
                </bk-dropdown>
              </template>
            </div>

            <div
              v-show="!collapsedGroups.has(group.name) && filteredGroupedHistory[group.name]?.length"
              class="group-children">
              <div
                v-for="conv in filteredGroupedHistory[group.name]"
                :key="conv.id"
                class="conv-item conv-item--indent"
                :class="{ 'is-active': activeId === conv.id, 'is-menu-open': activeMenuId === conv.id }"
                draggable="true"
                @click="$emit('select', conv.id)"
                @dragend="handleDragEnd"
                @dragstart.stop="handleDragStart($event, 'conversation', conv.id, group.name)">
                <span class="conv-dot">•</span>
                <template v-if="editingConvId === conv.id">
                  <bk-input
                    v-model="editConvTitle"
                    class="conv-title-input"
                    size="small"
                    @blur="cancelEditConv"
                    @click.stop
                    @enter="confirmEditConv(conv.id)" />
                </template>
                <template v-else>
                  <span class="conv-title">{{ conv.title }}</span>
                </template>
                <div class="conv-actions">
                  <bk-dropdown
                    :is-show="activeMenuId === conv.id"
                    placement="bottom-end"
                    trigger="click"
                    @click.stop
                    @hide="hideMenu"
                    @show="showMenu(conv.id)">
                    <ellipsis
                      class="action-btn"
                      :class="{ 'is-active': activeMenuId === conv.id }" />
                    <template #content>
                      <bk-dropdown-menu>
                        <bk-dropdown-item @click="handlePin(conv.id)">
                          置顶对话
                        </bk-dropdown-item>
                        <bk-dropdown-item @click="startEditConv(conv.id, conv.title)">
                          重命名
                        </bk-dropdown-item>
                        <bk-dropdown-item @click="moveToGroup(conv.id, undefined)">
                          移出分组
                        </bk-dropdown-item>
                        <bk-dropdown-item ext-cls="sub-menu-item">
                          <bk-dropdown
                            placement="right-start"
                            style="width: 100%"
                            trigger="hover">
                            <div class="dropdown-sub-trigger">
                              <span>移动到分组</span>
                              <angle-right class="sub-icon" />
                            </div>
                            <template #content>
                              <bk-dropdown-menu>
                                <bk-dropdown-item
                                  v-for="g in groups"
                                  :key="g.id"
                                  @click="moveToGroup(conv.id, g.name)">
                                  {{ g.name }}
                                </bk-dropdown-item>
                              </bk-dropdown-menu>
                            </template>
                          </bk-dropdown>
                        </bk-dropdown-item>
                        <bk-dropdown-item ext-cls="sub-menu-item">
                          <bk-dropdown
                            placement="right-start"
                            style="width: 100%"
                            trigger="hover">
                            <div class="dropdown-sub-trigger">
                              <span>导出</span>
                              <angle-right class="sub-icon" />
                            </div>
                            <template #content>
                              <bk-dropdown-menu>
                                <bk-dropdown-item @click="showExportDialog('json')">
                                  导出 JSON
                                </bk-dropdown-item>
                                <bk-dropdown-item @click="showExportDialog('markdown')">
                                  导出 Markdown
                                </bk-dropdown-item>
                                <bk-dropdown-item @click="showExportDialog('pdf')">
                                  导出 PDF
                                </bk-dropdown-item>
                              </bk-dropdown-menu>
                            </template>
                          </bk-dropdown>
                        </bk-dropdown-item>
                        <bk-dropdown-item @click="handleDelete(conv.id)">
                          删除对话
                        </bk-dropdown-item>
                      </bk-dropdown-menu>
                    </template>
                  </bk-dropdown>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 折叠状态：不显示任何菜单项，仅通过悬浮按钮展开 -->
    <template v-else>
      <div class="collapsed-placeholder" />
    </template>

    <!-- 悬浮工具栏（折叠态） -->
    <div
      v-if="collapsed"
      class="collapsed-toolbar">
      <div
        class="toolbar-item"
        @click="$emit('toggle')">
        <angle-right class="collapse-icon" />
      </div>
      <div
        class="toolbar-item"
        @click="$emit('new-chat')">
        <audit-icon type="add" />
      </div>
      <div
        class="toolbar-item"
        @click="handleSearchClick">
        <search />
      </div>
    </div>

    <!-- 悬浮折叠按钮（展开态） -->
    <div
      v-else
      class="collapse-btn"
      @click="$emit('toggle')">
      <audit-icon
        class="collapse-icon"
        type="navi-expand" />
    </div>

    <!-- 新建分组弹窗 -->
    <bk-dialog
      v-model:is-show="addGroupDialog.show"
      title="新建分组"
      :width="400"
      @confirm="confirmAddGroup">
      <div class="add-group-content">
        <bk-input
          v-model="addGroupDialog.name"
          placeholder="请输入分组名称"
          @enter="confirmAddGroup" />
      </div>
    </bk-dialog>

    <!-- 删除分组弹窗 -->
    <bk-dialog
      v-model:is-show="deleteGroupDialog.show"
      class="delete-group-dialog"
      header-align="center"
      title="是否删除该分组？">
      <div class="delete-group-content">
        <div class="group-name-display">
          分组：{{ deleteGroupDialog.groupName }}
        </div>
        <bk-checkbox
          v-model="deleteGroupDialog.deleteConversations"
          class="delete-checkbox">
          同步删除该分组下的所有对话
        </bk-checkbox>
        <div class="delete-warning-box">
          勾选后将同步删除该分组下的所有对话，请谨慎操作！
        </div>
      </div>
      <template #footer>
        <div class="delete-dialog-footer">
          <bk-button
            theme="danger"
            @click="confirmDeleteGroup">
            删除
          </bk-button>
          <bk-button @click="deleteGroupDialog.show = false">
            取消
          </bk-button>
        </div>
      </template>
    </bk-dialog>

    <!-- 导出对话弹窗 -->
    <bk-dialog
      v-model:is-show="exportDialog.show"
      title="导出对话"
      width="480"
      @closed="closeExportDialog"
      @confirm="confirmExport">
      <div class="export-dialog-content">
        <div class="select-all-wrap">
          <bk-checkbox
            v-model="isAllExportSelected"
            :indeterminate="exportIndeterminate"
            @change="handleSelectAllExport">
            全选 ({{ exportDialog.selectedIds.length }} / {{ props.conversations.length }})
          </bk-checkbox>
        </div>
        <div class="export-list">
          <div
            v-for="conv in props.conversations"
            :key="conv.id"
            class="export-item">
            <bk-checkbox
              :model-value="exportDialog.selectedIds.includes(conv.id)"
              @change="(val) => handleSelectExport(val, conv.id)">
              <span class="conv-name">{{ conv.title }}</span>
              <span class="conv-count">({{ conv.messages?.length || 0 }}条消息)</span>
            </bk-checkbox>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <bk-button
            :disabled="exportDialog.selectedIds.length === 0"
            theme="primary"
            @click="confirmExport">
            确认导出
          </bk-button>
          <bk-button @click="closeExportDialog">
            取消
          </bk-button>
        </div>
      </template>
    </bk-dialog>

    <!-- 导入对话弹窗 -->
    <bk-dialog
      v-model:is-show="importDialog.show"
      title="导入对话"
      width="480"
      @closed="closeImportDialog"
      @confirm="confirmImport">
      <div class="import-dialog-content">
        <bk-alert
          style="margin-bottom: 16px;"
          theme="warning"
          title="已有同名分组，导入的会话将合并到现有分组中" />
        <div class="select-all-wrap">
          <bk-checkbox
            v-model="isAllImportSelected"
            :indeterminate="importIndeterminate"
            @change="handleSelectAllImport">
            全选 ({{ importDialog.selectedIds.length }} / {{ importDialog.mockData.length }})
          </bk-checkbox>
        </div>
        <div class="import-list">
          <div
            v-for="conv in importDialog.mockData"
            :key="conv.id"
            class="import-item">
            <bk-checkbox
              :model-value="importDialog.selectedIds.includes(conv.id)"
              @change="(val) => handleSelectImport(val, conv.id)">
              <span class="conv-name">{{ conv.title }}</span>
              <span class="conv-count">({{ conv.messages?.length || 0 }}条消息)</span>
            </bk-checkbox>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <bk-button
            :disabled="importDialog.selectedIds.length === 0"
            theme="primary"
            @click="confirmImport">
            确认导入
          </bk-button>
          <bk-button @click="closeImportDialog">
            取消
          </bk-button>
        </div>
      </template>
    </bk-dialog>

    <!-- 清空所有对话弹窗 -->
    <bk-dialog
      v-model:is-show="clearAllDialog.show"
      class="clear-all-dialog"
      :show-header="false"
      width="480"
      @closed="closeClearAllDialog">
      <div class="clear-all-dialog-content">
        <audit-icon
          class="warning-icon-wrap"
          type="info-fill" />
        <div class="dialog-title">
          确定清空所有会话？
        </div>
        <div class="warning-text-box">
          此操作将删除所有会话及消息记录，包括已分组和未分组的共 <strong>{{ props.conversations.length }}</strong> 个会话。<br>
          <span class="danger-text">此操作不可恢复，请谨慎操作！</span>
        </div>
        <div class="confirm-input-wrap">
          <div class="input-label">
            请输入「确认清空」以继续
          </div>
          <bk-input
            v-model="clearAllDialog.confirmText"
            placeholder="确认清空" />
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer center">
          <bk-button
            :disabled="clearAllDialog.confirmText !== '确认清空'"
            theme="danger"
            @click="confirmClearAll">
            清空
          </bk-button>
          <bk-button @click="closeClearAllDialog">
            取消
          </bk-button>
        </div>
      </template>
    </bk-dialog>

    <!-- 报告列表面板 -->
    <div
      v-if="isReportListShow"
      class="report-list-panel"
      :style="{ width: panelWidth + 'px' }">
      <!-- 右侧竖排小圆点手柄（可拖拽调整宽度） -->
      <div
        class="panel-drag-handle"
        @mousedown="handlePanelDragStart">
        <span class="drag-dot" />
        <span class="drag-dot" />
        <span class="drag-dot" />
        <span class="drag-dot" />
        <span class="drag-dot" />
        <span class="drag-dot" />
      </div>
      <div class="panel-header">
        <span class="title">报告列表</span>
        <close
          class="close-icon"
          @click="closeReportList" />
      </div>
      <div class="panel-search">
        <bk-input
          v-model="reportSearchKeyword"
          clearable
          placeholder="搜索报告标题、IP 地址、会话名称...">
          <template #prefix>
            <search class="search-icon" />
          </template>
        </bk-input>
      </div>
      <div class="panel-tabs">
        <div class="tabs-wrapper">
          <div
            v-for="tab in reportTabs"
            :key="tab.id"
            class="tab-item"
            :class="{ 'is-active': activeReportTab === tab.id }"
            @click="activeReportTab = tab.id">
            {{ tab.name }} <span class="count">{{ tab.count }}</span>
          </div>
        </div>
      </div>
      <div class="panel-content">
        <bk-collapse
          v-model="activeReportPanels"
          class="report-collapse">
          <bk-collapse-panel
            v-for="category in filteredReportCategories"
            :key="category.id"
            :name="category.id">
            <template #header>
              <div class="group-header">
                {{ category.name }} <span class="count">{{ category.reports.length }}</span>
              </div>
            </template>
            <template #content>
              <div class="report-list">
                <div
                  v-for="report in category.reports"
                  :key="report.id"
                  class="report-item"
                  :class="{ 'is-active': activeDropdownReport === report.name }"
                  @click="handleReportClick(report)">
                  <div
                    class="report-icon-wrap"
                    :class="{ warning: report.isWarning }">
                    <text-file class="report-icon" />
                  </div>
                  <div class="report-content">
                    <div class="report-name">
                      <span
                        v-if="report.isWarning"
                        class="warning-icon">⚠️</span>{{ report.name }}
                    </div>
                    <div class="report-time">
                      {{ report.time }}
                    </div>
                    <div
                      class="report-actions"
                      @click.stop>
                      <bk-dropdown
                        placement="bottom-end"
                        trigger="click"
                        @hide="handleDropdownHide"
                        @show="handleDropdownShow(report.name)">
                        <span class="action-icon">
                          <audit-icon
                            class="download-icon"
                            type="download" />
                          <span class="action-text">导出</span>
                        </span>
                        <template #content>
                          <bk-dropdown-menu>
                            <bk-dropdown-item @click="handleExport('markdown')">
                              导出 Markdown
                            </bk-dropdown-item>
                            <bk-dropdown-item @click="handleExport('pdf')">
                              导出 PDF
                            </bk-dropdown-item>
                          </bk-dropdown-menu>
                        </template>
                      </bk-dropdown>
                      <span
                        class="action-text jump-text"
                        @click="handleLocateConversation">跳转</span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </bk-collapse-panel>
        </bk-collapse>
      </div>
    </div>
    <bk-sideslider
      v-model:isShow="isReportDetailShow"
      quick-close
      title="报告详情"
      :width="800">
      <template #header>
        <div class="report-detail-header">
          <span class="title">{{ currentReport?.name || '报告详情' }}</span>
          <div class="actions">
            <bk-dropdown
              placement="bottom-end"
              trigger="click">
              <bk-button>
                <audit-icon
                  class="download-icon"
                  type="download" />
                导出
              </bk-button>
              <template #content>
                <bk-dropdown-menu>
                  <bk-dropdown-item @click="handleExport('markdown')">
                    导出 Markdown
                  </bk-dropdown-item>
                  <bk-dropdown-item @click="handleExport('pdf')">
                    导出 PDF
                  </bk-dropdown-item>
                </bk-dropdown-menu>
              </template>
            </bk-dropdown>
            <bk-button @click="handleLocateConversation">
              跳转至会话
            </bk-button>
          </div>
        </div>
      </template>
      <template #default>
        <div class="report-detail-content">
          <div class="markdown-body">
            <p>这里是报告的 Markdown 内容...</p>
          </div>
        </div>
      </template>
    </bk-sideslider>
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed, watch, nextTick } from 'vue';
  import { AngleRight, Search, Folder, FolderShape, Ellipsis, Plus, Close, TextFile } from 'bkui-vue/lib/icon';

  interface Conversation {
    id: string;
    title: string;
    pinned: boolean;
    groupName?: string;
    messages: any[];
    createdAt: number;
  }

  interface Group {
    id: string;
    name: string;
  }

  const props = defineProps<{
    collapsed: boolean;
    conversations: Conversation[];
    groups: Group[];
    activeId: string | null;
  }>();

  const emit = defineEmits<{
    toggle: [];
    'new-chat': [];
    select: [id: string];
    delete: [id: string];
    pin: [id: string];
    'update-group': [id: string, groupName?: string];
    'update-groups': [groups: Group[]];
    'delete-group': [groupName: string, keepConversations: boolean];
    'clear-all': [];
    'export': [type: string, ids: string[]];
    'import': [ids: string[]];
    'update-conv-title': [id: string, title: string];
  }>();

  const searchKeyword = ref('');
  const searchInputRef = ref<HTMLInputElement | null>(null);
  const isDropdownShow = ref(false);
  const isSearchClicked = ref(false);

  // 报告列表相关
  const isReportListShow = ref(false);
  const reportSearchKeyword = ref('');
  const activeReportPanels = ref(['behavior', 'alarm', 'other']);
  const activeReportTab = ref('all');
  const panelWidth = ref(360);
  const PANEL_MIN_WIDTH = 420;
  const PANEL_MAX_WIDTH = 600;

  // 报告分类数据
  const reportCategories = ref([
    {
      id: 'behavior',
      name: '多主机行为分析',
      reports: [
        { id: 'r1', name: '多主机行为分析报告', time: '2026-03-27 11:32', isWarning: false },
        { id: 'r2', name: '主机行为分析报告', time: '2026-03-27 11:32', isWarning: false },
      ],
    },
    {
      id: 'alarm',
      name: '风险告警解读',
      reports: [
        { id: 'r3', name: '高危风险告警解读', time: '2026-03-27 11:32', isWarning: true },
      ],
    },
    {
      id: 'other',
      name: '其他',
      reports: [
        { id: 'r4', name: '安全事件调查报告', time: '2026-03-27 11:32', isWarning: false },
      ],
    },
  ]);

  // 标签页数据
  const reportTabs = computed(() => {
    const tabs = [
      { id: 'all', name: '全部', count: reportCategories.value.reduce((sum, cat) => sum + cat.reports.length, 0) },
    ];
    reportCategories.value.forEach((cat) => {
      tabs.push({
        id: cat.id,
        name: cat.name,
        count: cat.reports.length,
      });
    });
    return tabs;
  });

  // 过滤后的报告分类
  const filteredReportCategories = computed(() => {
    if (activeReportTab.value === 'all') {
      return reportCategories.value;
    }
    return reportCategories.value.filter(cat => cat.id === activeReportTab.value);
  });

  const isReportDetailShow = ref(false);
  const currentReport = ref<any>(null);
  const activeDropdownReport = ref<string | null>(null);

  const handleDropdownShow = (reportName: string) => {
    activeDropdownReport.value = reportName;
  };

  const handleDropdownHide = () => {
    activeDropdownReport.value = null;
  };

  const handleReportClick = (report: any) => {
    currentReport.value = report;
    isReportDetailShow.value = true;
  };

  const handleExport = (type: string) => {
    console.log('export', type);
  };

  const handleLocateConversation = () => {
    console.log('locate conversation');
  };

  const showReportList = () => {
    isReportListShow.value = true;
    isDropdownShow.value = false;
  };

  const closeReportList = () => {
    isReportListShow.value = false;
  };

  // 面板宽度拖拽调整
  const handlePanelDragStart = (e: MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = panelWidth.value;

    const onDragMove = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const newWidth = startWidth + deltaX;
      panelWidth.value = Math.min(PANEL_MAX_WIDTH, Math.max(PANEL_MIN_WIDTH, newWidth));
    };

    const onDragEnd = () => {
      document.removeEventListener('mousemove', onDragMove);
      document.removeEventListener('mouseup', onDragEnd);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', onDragEnd);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const handleSearchClick = () => {
    isSearchClicked.value = true;
    emit('toggle');
  };

  watch(() => props.collapsed, async (newVal) => {
    if (!newVal && isSearchClicked.value) {
      isSearchClicked.value = false;
      await nextTick();
      searchInputRef.value?.focus();
    }
  });

  const pinnedConversations = computed(() => props.conversations.filter(c => c.pinned));
  const historyConversations = computed(() => props.conversations.filter(c => !c.pinned));

  const filteredPinned = computed(() => {
    if (!searchKeyword.value) return pinnedConversations.value;
    return pinnedConversations.value.filter(c => c.title.includes(searchKeyword.value));
  });

  const filteredUngroupedHistory = computed(() => {
    const ungrouped = historyConversations.value.filter(c => !c.groupName);
    if (!searchKeyword.value) return ungrouped;
    return ungrouped.filter(c => c.title.includes(searchKeyword.value));
  });

  const filteredGroupedHistory = computed(() => {
    const grouped: Record<string, Conversation[]> = {};
    // Initialize all groups
    props.groups.forEach((g) => {
      grouped[g.name] = [];
    });
    const groupedConvs = historyConversations.value.filter(c => c.groupName);
    for (const conv of groupedConvs) {
      if (searchKeyword.value && !conv.title.includes(searchKeyword.value)) continue;
      const key = conv.groupName!;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(conv);
    }
    return grouped;
  });

  // 监听分组内容变化，如果分组内容为0，则自动删除该分组
  watch(filteredGroupedHistory, (newVal) => {
    // 只有在非搜索状态下才自动删除空分组，避免搜索时误删
    if (searchKeyword.value) return;

    const emptyGroups = Object.keys(newVal).filter(groupName => newVal[groupName].length === 0);
    if (emptyGroups.length > 0) {
      const newGroups = props.groups.filter(g => !emptyGroups.includes(g.name));
      if (newGroups.length !== props.groups.length) {
        emit('update-groups', newGroups);
      }
    }
  }, { deep: true });

  // 分组折叠状态
  const collapsedGroups = ref<Set<string>>(new Set());

  const toggleGroup = (groupName: string) => {
    if (collapsedGroups.value.has(groupName)) {
      collapsedGroups.value.delete(groupName);
    } else {
      collapsedGroups.value.add(groupName);
    }
  };

  // 拖拽状态
  const dragState = ref<{
    type: 'group' | 'conversation' | null;
    id: string | null;
    sourceGroup?: string;
  }>({ type: null, id: null });

  const dragOverState = ref<{
    type: 'group' | 'conversation' | null;
    id: string | null;
    position: 'top' | 'bottom' | 'inside' | null;
  }>({ type: null, id: null, position: null });

  const getGroupItemDragClass = (groupName: string) => ({
    'is-drag-over-top': dragOverState.value.type === 'group'
      && dragOverState.value.id === groupName
      && dragOverState.value.position === 'top',
    'is-drag-over-bottom': dragOverState.value.type === 'group'
      && dragOverState.value.id === groupName
      && dragOverState.value.position === 'bottom',
  });

  const getGroupHeaderDragClass = (groupName: string) => ({
    'is-drag-over-inside': dragOverState.value.type === 'group'
      && dragOverState.value.id === groupName
      && dragOverState.value.position === 'inside',
  });

  // 拖拽处理
  const handleDragStart = (e: DragEvent, type: 'group' | 'conversation', id: string, sourceGroup?: string) => {
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', JSON.stringify({ type, id, sourceGroup }));
    }
    dragState.value = { type, id, sourceGroup };
  };

  const handleDragOver = (e: DragEvent, type: 'group' | 'conversation', id: string) => {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'move';
    }

    if (dragState.value.type === 'conversation' && type === 'group') {
      dragOverState.value = { type, id, position: 'inside' };
    } else if (dragState.value.type === 'group' && type === 'group') {
      const targetRect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      const midY = targetRect.top + targetRect.height / 2;
      const position = e.clientY < midY ? 'top' : 'bottom';
      dragOverState.value = { type, id, position };
    } else if (dragState.value.type === 'conversation' && type === 'conversation') {
      // 暂不支持会话排序，只支持移动到分组
      dragOverState.value = { type: null, id: null, position: null };
    }
  };

  const handleDragLeave = () => {
    dragOverState.value = { type: null, id: null, position: null };
  };

  const handleDrop = (e: DragEvent, targetType: 'group' | 'conversation', targetId: string) => {
    e.preventDefault();
    const { type, id } = dragState.value;
    const { position } = dragOverState.value;

    if (type === 'conversation' && targetType === 'group') {
      // 移动会话到分组
      emit('update-group', id!, targetId);
    } else if (type === 'group' && targetType === 'group' && id !== targetId) {
      // 分组排序
      const newGroups = [...props.groups];
      const sourceIndex = newGroups.findIndex(g => g.name === id);
      const targetIndex = newGroups.findIndex(g => g.name === targetId);

      if (sourceIndex !== -1 && targetIndex !== -1) {
        const [movedGroup] = newGroups.splice(sourceIndex, 1);
        const insertIndex = position === 'top' ? targetIndex : targetIndex + 1;
        newGroups.splice(insertIndex, 0, movedGroup);
        emit('update-groups', newGroups);
      }
    }

    dragState.value = { type: null, id: null };
    dragOverState.value = { type: null, id: null, position: null };
  };

  const handleDragEnd = () => {
    dragState.value = { type: null, id: null };
    dragOverState.value = { type: null, id: null, position: null };
  };

  // 新建分组弹窗
  const addGroupDialog = ref({
    show: false,
    name: '',
  });

  const showAddGroupDialog = () => {
    addGroupDialog.value.show = true;
    addGroupDialog.value.name = '';
  };

  const confirmAddGroup = () => {
    if (addGroupDialog.value.name.trim()) {
      const newGroups = [...props.groups, { id: `g_${Date.now()}`, name: addGroupDialog.value.name.trim() }];
      emit('update-groups', newGroups);
    }
    addGroupDialog.value.show = false;
  };

  // 重命名分组
  const editingGroup = ref<string | null>(null);
  const editGroupName = ref('');
  const editGroupInputRef = ref<HTMLInputElement | null>(null);

  const startEditGroup = async (groupName: string) => {
    editingGroup.value = groupName;
    editGroupName.value = groupName;
    hideGroupMenu();
    await nextTick();
    editGroupInputRef.value?.focus();
  };

  const confirmEditGroup = (oldName: string) => {
    const newName = editGroupName.value.trim();
    if (newName && newName !== oldName) {
      const newGroups = props.groups.map(g => (g.name === oldName ? { ...g, name: newName } : g));
      emit('update-groups', newGroups);
      // 更新该分组下的所有会话
      props.conversations.forEach((c) => {
        if (c.groupName === oldName) {
          emit('update-group', c.id, newName);
        }
      });
    }
    editingGroup.value = null;
  };

  const cancelEditGroup = () => {
    editingGroup.value = null;
  };

  // 重命名会话
  const editingConvId = ref<string | null>(null);
  const editConvTitle = ref('');
  const editConvInputRef = ref<any>(null);

  const startEditConv = async (id: string, title: string) => {
    editingConvId.value = id;
    editConvTitle.value = title;
    hideMenu();
    await nextTick();
    if (Array.isArray(editConvInputRef.value)) {
      editConvInputRef.value[0]?.focus();
    } else {
      editConvInputRef.value?.focus();
    }
  };

  const confirmEditConv = (id: string) => {
    const newTitle = editConvTitle.value.trim();
    if (newTitle) {
      emit('update-conv-title', id, newTitle);
    }
    editingConvId.value = null;
  };

  const cancelEditConv = () => {
    editingConvId.value = null;
  };

  // 删除分组弹窗
  const deleteGroupDialog = ref({
    show: false,
    groupName: '',
    deleteConversations: false,
  });

  const showDeleteGroup = (groupName: string) => {
    deleteGroupDialog.value = {
      show: true,
      groupName,
      deleteConversations: false,
    };
    hideGroupMenu();
  };

  const confirmDeleteGroup = () => {
    emit('delete-group', deleteGroupDialog.value.groupName, !deleteGroupDialog.value.deleteConversations);
    deleteGroupDialog.value.show = false;
  };

  // 会话操作菜单
  const activeMenuId = ref<string | null>(null);
  const activeGroupMenuId = ref<string | null>(null);

  const showMenu = (id: string) => {
    activeMenuId.value = id;
  };

  const hideMenu = () => {
    activeMenuId.value = null;
  };

  const showGroupMenu = (name: string) => {
    activeGroupMenuId.value = name;
  };

  const hideGroupMenu = () => {
    activeGroupMenuId.value = null;
  };

  const moveToGroup = (convId: string, groupName?: string) => {
    emit('update-group', convId, groupName);
    hideMenu();
  };

  const handlePin = (convId: string) => {
    emit('pin', convId);
    hideMenu();
  };

  const handleDelete = (convId: string) => {
    emit('delete', convId);
    hideMenu();
  };

  // 导出对话逻辑
  const exportDialog = ref({
    show: false,
    type: '',
    selectedIds: [] as string[],
  });

  const isAllExportSelected = computed({
    get: () => {
      if (props.conversations.length === 0) return false;
      return exportDialog.value.selectedIds.length === props.conversations.length;
    },
    set: (val) => {
      if (val) {
        exportDialog.value.selectedIds = props.conversations.map(c => c.id);
      } else {
        exportDialog.value.selectedIds = [];
      }
    },
  });

  const exportIndeterminate = computed(() => {
    const selectedCount = exportDialog.value.selectedIds.length;
    return selectedCount > 0 && selectedCount < props.conversations.length;
  });

  const showExportDialog = (type: string) => {
    exportDialog.value.type = type;
    exportDialog.value.selectedIds = [];
    exportDialog.value.show = true;
    isDropdownShow.value = false;
    hideMenu();
    hideGroupMenu();
  };

  const handleSelectAllExport = (val: boolean) => {
    isAllExportSelected.value = val;
  };

  const handleSelectExport = (val: boolean, id: string) => {
    if (val) {
      exportDialog.value.selectedIds.push(id);
    } else {
      exportDialog.value.selectedIds = exportDialog.value.selectedIds.filter(i => i !== id);
    }
  };

  const closeExportDialog = () => {
    exportDialog.value.show = false;
  };

  const confirmExport = () => {
    if (exportDialog.value.selectedIds.length === 0) return;
    emit('export', exportDialog.value.type, exportDialog.value.selectedIds);
    closeExportDialog();
  };

  // 导入对话逻辑
  const importDialog = ref({
    show: false,
    selectedIds: [] as string[],
    mockData: [
      { id: 'mock1', title: '网络流量异常', messages: new Array(3) },
      { id: 'mock2', title: '主机行为分析', messages: new Array(8) },
      { id: 'mock3', title: '风险告警解读', messages: new Array(12) },
      { id: 'mock4', title: '高危风险任务', messages: new Array(5) },
    ],
  });

  const isAllImportSelected = computed({
    get: () => {
      if (importDialog.value.mockData.length === 0) return false;
      return importDialog.value.selectedIds.length === importDialog.value.mockData.length;
    },
    set: (val) => {
      if (val) {
        importDialog.value.selectedIds = importDialog.value.mockData.map(c => c.id);
      } else {
        importDialog.value.selectedIds = [];
      }
    },
  });

  const importIndeterminate = computed(() => {
    const selectedCount = importDialog.value.selectedIds.length;
    return selectedCount > 0 && selectedCount < importDialog.value.mockData.length;
  });

  const showImportDialog = () => {
    importDialog.value.selectedIds = [];
    importDialog.value.show = true;
    isDropdownShow.value = false;
  };

  const handleSelectAllImport = (val: boolean) => {
    isAllImportSelected.value = val;
  };

  const handleSelectImport = (val: boolean, id: string) => {
    if (val) {
      importDialog.value.selectedIds.push(id);
    } else {
      importDialog.value.selectedIds = importDialog.value.selectedIds.filter(i => i !== id);
    }
  };

  const closeImportDialog = () => {
    importDialog.value.show = false;
  };

  const confirmImport = () => {
    if (importDialog.value.selectedIds.length === 0) return;
    emit('import', importDialog.value.selectedIds);
    closeImportDialog();
  };

  // 清空所有对话逻辑
  const clearAllDialog = ref({
    show: false,
    confirmText: '',
  });

  const showClearAllDialog = () => {
    clearAllDialog.value.confirmText = '';
    clearAllDialog.value.show = true;
    isDropdownShow.value = false;
  };

  const closeClearAllDialog = () => {
    clearAllDialog.value.show = false;
  };

  const confirmClearAll = () => {
    if (clearAllDialog.value.confirmText === '确认清空') {
      emit('clear-all');
      closeClearAllDialog();
    }
  };
</script>

<style
  lang="postcss"
  src="./chat-sidebar.css" />
