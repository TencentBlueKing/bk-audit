<template>
  <div
    ref="sidebarRootRef"
    class="chat-sidebar"
    :class="{ 'is-collapsed': collapsed }">
    <template v-if="!collapsed">
      <!-- 场景选择 -->
      <div class="sidebar-project">
        <scene-system-selector
          ref="sceneSelectorRef"
          v-model="selectedScene"
          :popover-width="224"
          scene-permission="view_scene"
          system-permission="view_system"
          width="100%"
          @change="handleSceneChange" />
      </div>

      <!-- 搜索区：搜索框 + 筛选按钮 -->
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
          :key="filterDropdownKey"
          ref="filterDropdownRef"
          :is-show="isDropdownShow"
          placement="bottom-start"
          trigger="click"
          @hide="handleFilterDropdownHide"
          @show="isDropdownShow = true">
          <div
            class="filter-btn"
            :class="{ 'is-active': isDropdownShow }"
            title="更多操作">
            <img
              alt=""
              class="filter-icon"
              :src="aiSettingIcon">
          </div>
          <template #content>
            <bk-dropdown-menu>
              <bk-dropdown-item ext-cls="sub-menu-item">
                <bk-dropdown
                  ref="exportSubmenuRef"
                  :is-show="isExportSubmenuShow"
                  placement="right-start"
                  style="width: 100%"
                  trigger="hover"
                  @hide="isExportSubmenuShow = false"
                  @show="isExportSubmenuShow = true">
                  <div class="dropdown-sub-trigger">
                    <span>导出会话</span>
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
                导入会话
              </bk-dropdown-item>
              <bk-dropdown-item @click="showReportList">
                报告列表
              </bk-dropdown-item>
              <bk-dropdown-item @click="showClearAllDialog">
                清空所有会话
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
          <img
            alt=""
            class="new-chat-icon"
            :src="aiAddIcon">
          新对话
        </div>
      </div>

      <!-- 对话列表 -->
      <div class="conversation-list">
        <!-- 历史对话（未分组，置顶优先） -->
        <div class="conv-section">
          <div class="section-label">
            <span class="label-text">历史对话</span>
            <bk-popover
              arrow
              ext-cls="add-group-popover"
              :is-show="addGroupDialog.show"
              placement="bottom-end"
              theme="light"
              trigger="click"
              :width="260"
              @after-show="handleAddGroupPopoverShow"
              @update:is-show="onAddGroupShowChange">
              <span
                class="label-action"
                :class="{ 'is-active': addGroupDialog.show }">
                <plus />
              </span>
              <template #content>
                <div
                  class="add-group-popover-content"
                  @click.stop>
                  <div class="add-group-title">
                    新建分组
                  </div>
                  <bk-input
                    ref="addGroupInputRef"
                    v-model="addGroupDialog.name"
                    placeholder="请输入分组名称"
                    @enter="confirmAddGroup" />
                  <div class="add-group-footer">
                    <bk-button
                      theme="primary"
                      @click="confirmAddGroup">
                      确定
                    </bk-button>
                    <bk-button @click="closeAddGroupPopover">
                      取消
                    </bk-button>
                  </div>
                </div>
              </template>
            </bk-popover>
          </div>

          <div
            v-for="conv in filteredHistoryList"
            :key="conv.id"
            class="conv-item"
            :class="{
              'is-active': activeId === conv.id && editingConvId !== conv.id,
              'is-menu-open': activeMenuId === conv.id,
            }"
            draggable="true"
            @click="$emit('select', conv.id)"
            @dragend="handleDragEnd"
            @dragstart="handleDragStart($event, 'conversation', conv.id)">
            <span class="conv-dot">•</span>
            <template v-if="editingConvId === conv.id">
              <bk-input
                ref="editConvInputRef"
                v-model="editConvTitle"
                autofocus
                class="conv-title-input"
                size="small"
                @blur="cancelEditConv"
                @click.stop
                @enter="confirmEditConv(conv.id)" />
            </template>
            <template v-else>
              <span class="conv-title">{{ conv.title }}</span>
            </template>
            <div
              class="conv-actions"
              :class="{ 'is-pinned-actions': conv.pinned }"
              @click.stop
              @mousedown.stop>
              <bk-dropdown
                class="more-dropdown"
                placement="bottom-end"
                :popover-options="{ extCls: 'chat-conv-dropdown-pop' }"
                trigger="click"
                @hide="hideMenu"
                @show="showMenu(conv.id)">
                <div
                  class="action-btn"
                  :class="{ 'is-active': activeMenuId === conv.id }">
                  <audit-icon type="more" />
                </div>
                <template #content>
                  <bk-dropdown-menu>
                    <bk-dropdown-item @click="handlePin(conv.id)">
                      {{ conv.pinned ? '取消置顶' : '置顶' }}
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
                    <bk-dropdown-item @click="handleDelete(conv)">
                      删除
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
              <img
                v-if="collapsedGroups.has(group.name)"
                alt=""
                class="group-icon"
                :src="folderEmptyIcon">
              <img
                v-else
                alt=""
                class="group-icon"
                :src="folderIcon">

              <template v-if="editingGroup === group.name">
                <bk-input
                  ref="editGroupInputRef"
                  v-model="editGroupName"
                  autofocus
                  size="small"
                  @blur="cancelEditGroup"
                  @click.stop
                  @enter="confirmEditGroup(group.name)" />
              </template>
              <template v-else>
                <span class="group-name">
                  {{ group.name }}
                  <span class="group-count">({{ filteredGroupedHistory[group.name]?.length || 0 }})</span>
                </span>
                <bk-dropdown
                  class="group-more-dropdown"
                  placement="bottom-end"
                  :popover-options="{ extCls: 'chat-group-dropdown-pop' }"
                  trigger="click"
                  @click.stop
                  @hide="hideGroupMenu"
                  @mousedown.stop
                  @show="showGroupMenu(group.name)">
                  <div
                    class="group-more"
                    :class="{ 'is-active': activeGroupMenuId === group.name }">
                    <audit-icon type="more" />
                  </div>
                  <template #content>
                    <bk-dropdown-menu>
                      <bk-dropdown-item @click="startEditGroup(group.name)">
                        重命名
                      </bk-dropdown-item>
                      <bk-dropdown-item ext-cls="sub-menu-item">
                        <bk-dropdown
                          placement="right-start"
                          style="width: 100%"
                          trigger="hover">
                          <div class="dropdown-sub-trigger">
                            <span>导出会话</span>
                            <angle-right class="sub-icon" />
                          </div>
                          <template #content>
                            <bk-dropdown-menu>
                              <bk-dropdown-item @click="showGroupExportDialog('json', group.name)">
                                导出 JSON
                              </bk-dropdown-item>
                              <bk-dropdown-item @click="showGroupExportDialog('markdown', group.name)">
                                导出 Markdown
                              </bk-dropdown-item>
                              <bk-dropdown-item @click="showGroupExportDialog('pdf', group.name)">
                                导出 PDF
                              </bk-dropdown-item>
                            </bk-dropdown-menu>
                          </template>
                        </bk-dropdown>
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
                :class="{
                  'is-active': activeId === conv.id && editingConvId !== conv.id,
                  'is-menu-open': activeMenuId === conv.id,
                }"
                draggable="true"
                @click="$emit('select', conv.id)"
                @dragend="handleDragEnd"
                @dragstart.stop="handleDragStart($event, 'conversation', conv.id, group.name)">
                <span class="conv-dot">•</span>
                <template v-if="editingConvId === conv.id">
                  <bk-input
                    ref="editConvInputRef"
                    v-model="editConvTitle"
                    autofocus
                    class="conv-title-input"
                    size="small"
                    @blur="cancelEditConv"
                    @click.stop
                    @enter="confirmEditConv(conv.id)" />
                </template>
                <template v-else>
                  <span class="conv-title">{{ conv.title }}</span>
                </template>
                <div
                  class="conv-actions"
                  @click.stop
                  @mousedown.stop>
                  <bk-dropdown
                    class="more-dropdown"
                    placement="bottom-end"
                    :popover-options="{ extCls: 'chat-conv-dropdown-pop' }"
                    trigger="click"
                    @hide="hideMenu"
                    @show="showMenu(conv.id)">
                    <div
                      class="action-btn"
                      :class="{ 'is-active': activeMenuId === conv.id }">
                      <audit-icon type="more" />
                    </div>
                    <template #content>
                      <bk-dropdown-menu>
                        <bk-dropdown-item @click="handlePin(conv.id)">
                          置顶
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
                        <bk-dropdown-item @click="handleDelete(conv)">
                          删除
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
        v-bk-tooltips="{ content: '展开侧栏', placement: 'right' }"
        class="toolbar-item"
        @click="handleCollapsedToggle">
        <angle-right class="toolbar-icon expand-icon" />
      </div>
      <div
        v-bk-tooltips="{ content: '新对话', placement: 'right' }"
        class="toolbar-item"
        @click="handleCollapsedNewChat">
        <img
          alt=""
          class="toolbar-icon add-icon"
          :src="aiAddIcon">
      </div>
      <div
        ref="collapsedSearchButtonRef"
        v-bk-tooltips="{ content: '搜索对话', placement: 'right' }"
        class="toolbar-item"
        @click="openCollapsedSearch">
        <search class="toolbar-icon search-icon" />
      </div>
    </div>

    <!-- 折叠态：搜索下拉面板 -->
    <div
      v-if="isCollapsedSearchOpen"
      class="collapsed-search-popover"
      :style="collapsedSearchPanelStyle">
      <div class="collapsed-search-cards">
        <div class="collapsed-search-card">
          <div class="collapsed-search-input-row">
            <input
              ref="collapsedSearchInputRef"
              v-model="collapsedSearchKeyword"
              class="collapsed-search-input"
              placeholder="搜索对话"
              type="search">
            <search class="collapsed-search-icon" />
          </div>

          <div class="collapsed-search-section">
            <div class="collapsed-search-section-title">
              最近对话 ({{ collapsedFilteredHistoryList.length }})
            </div>
            <div class="collapsed-search-scroll-wrap">
              <scroll-faker
                :key="`collapsed-search-${collapsedSearchKeyword}-${collapsedFilteredHistoryList.length}`">
                <div class="collapsed-search-list">
                  <div
                    v-for="conv in collapsedFilteredHistoryList"
                    :key="conv.id"
                    class="collapsed-search-item"
                    @click="handleCollapsedSelect(conv.id)">
                    <span class="collapsed-bullet">•</span>
                    <!-- eslint-disable vue/no-v-html -->
                    <span
                      class="collapsed-item-title"
                      v-html="getHighlightedTitle(conv.title)" />
                    <!-- eslint-enable vue/no-v-html -->
                  </div>
                </div>
              </scroll-faker>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 悬浮折叠按钮（展开态） -->
    <div
      v-else
      class="collapse-btn"
      @click="$emit('toggle')">
      <angle-left class="collapse-icon" />
    </div>

    <!-- 删除分组弹窗：通过 InfoBox 复用同类删除确认样式 -->

    <!-- 导出会话弹窗 -->
    <bk-dialog
      v-model:is-show="exportDialog.show"
      class="session-select-dialog"
      ext-cls="session-select-dialog"
      title="导出会话"
      :width="480"
      @after-show="closeSidebarPopovers"
      @closed="closeExportDialog"
      @confirm="confirmExport">
      <div class="export-dialog-content">
        <div class="export-list">
          <div class="export-item select-all-item">
            <bk-checkbox
              v-model="isAllExportSelected"
              :indeterminate="exportIndeterminate"
              @change="handleSelectAllExport">
              <span class="select-all-text">
                全选 ( {{ exportDialog.selectedIds.length }}/{{ props.conversations.length }} )
              </span>
            </bk-checkbox>
          </div>
          <div
            v-for="conv in props.conversations"
            :key="conv.id"
            class="export-item">
            <bk-checkbox
              :model-value="exportDialog.selectedIds.includes(conv.id)"
              @change="(val) => handleSelectExport(val, conv.id)">
              <span class="conv-name">{{ conv.title }}</span>
              <span class="conv-count">( {{ conv.messages?.length || 0 }}条消息 )</span>
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

    <!-- 导入会话弹窗 -->
    <bk-dialog
      v-model:is-show="importDialog.show"
      class="session-select-dialog"
      ext-cls="session-select-dialog"
      title="导入会话"
      :width="480"
      @after-show="closeSidebarPopovers"
      @closed="closeImportDialog"
      @confirm="confirmImport">
      <div class="import-dialog-content">
        <bk-alert
          class="import-alert"
          theme="warning"
          title="已有同名分组，导入的会话将合并到现有分组中" />
        <div class="import-list">
          <div class="import-item select-all-item">
            <bk-checkbox
              v-model="isAllImportSelected"
              :indeterminate="importIndeterminate"
              @change="handleSelectAllImport">
              <span class="select-all-text">
                全选 ( {{ importDialog.selectedIds.length }}/{{ importDialog.mockData.length }} )
              </span>
            </bk-checkbox>
          </div>
          <div
            v-for="conv in importDialog.mockData"
            :key="conv.id"
            class="import-item">
            <bk-checkbox
              :model-value="importDialog.selectedIds.includes(conv.id)"
              @change="(val) => handleSelectImport(val, conv.id)">
              <span class="conv-name">{{ conv.title }}</span>
              <span class="conv-count">( {{ conv.messages?.length || 0 }}条消息 )</span>
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
  import { computed, h, nextTick, onUnmounted, ref, watch } from 'vue';
  import { InfoBox } from 'bkui-vue';
  import { AngleLeft, AngleRight, Search, Plus, Close, TextFile } from 'bkui-vue/lib/icon';

  import useMessage from '@hooks/use-message';

  import ScrollFaker from '@components/scroll-faker/index.vue';
  import SceneSystemSelector from '@components/scene-system-selector/index.vue';

  import aiAddIcon from '@images/ai-add.svg';
  import aiSettingIcon from '@images/ai-setting.svg';
  import folderEmptyIcon from '@images/folder-empty.svg';
  import folderIcon from '@images/folder.svg';

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

  interface SceneItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
  }

  interface DropdownRefExpose {
    hide?: () => void;
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

  const { messageSuccess } = useMessage();

  const sidebarRootRef = ref<HTMLElement | null>(null);
  const searchKeyword = ref('');
  const searchInputRef = ref<HTMLInputElement | null>(null);
  const isDropdownShow = ref(false);
  const isExportSubmenuShow = ref(false);
  const filterDropdownKey = ref(0);
  const filterDropdownRef = ref<DropdownRefExpose | null>(null);
  const exportSubmenuRef = ref<DropdownRefExpose | null>(null);
  const sceneSelectorRef = ref<InstanceType<typeof SceneSystemSelector>>();

  const handleFilterDropdownHide = () => {
    isDropdownShow.value = false;
    isExportSubmenuShow.value = false;
  };

  const closeFilterDropdown = (forceRemount = false) => {
    isDropdownShow.value = false;
    isExportSubmenuShow.value = false;
    filterDropdownRef.value?.hide?.();
    exportSubmenuRef.value?.hide?.();
    if (forceRemount) {
      filterDropdownKey.value += 1;
    }
  };

  const closeSidebarPopovers = () => {
    closeFilterDropdown(true);
    sceneSelectorRef.value?.close?.();
  };

  // 折叠态搜索下拉面板
  const isCollapsedSearchOpen = ref(false);
  const collapsedSearchKeyword = ref('');
  const collapsedSearchInputRef = ref<HTMLInputElement | null>(null);
  const collapsedSearchButtonRef = ref<HTMLElement | null>(null);
  const collapsedSearchPanelStyle = ref<Record<string, string>>({
    left: '56px',
    top: '70px',
  });

  const selectedScene = ref<SceneItem | null>(null);

  const handleSceneChange = (value: SceneItem | null) => {
    selectedScene.value = value;
  };

  const handleCollapsedToggle = () => {
    isCollapsedSearchOpen.value = false;
    emit('toggle');
  };

  const handleCollapsedNewChat = () => {
    isCollapsedSearchOpen.value = false;
    emit('new-chat');
  };

  const handleCollapsedSelect = (id: string) => {
    emit('select', id);
    closeCollapsedSearch();
  };

  const updateCollapsedSearchPanelPosition = () => {
    const rootEl = sidebarRootRef.value;
    const btnEl = collapsedSearchButtonRef.value;
    if (!rootEl || !btnEl) return;

    const rootRect = rootEl.getBoundingClientRect();
    const btnRect = btnEl.getBoundingClientRect();
    // 面板显示在搜索按钮右侧，略微上移以对齐截图观感
    collapsedSearchPanelStyle.value = {
      left: `${btnRect.right - rootRect.left + 8}px`,
      top: `${Math.max(8, btnRect.top - rootRect.top - 12)}px`,
    };
  };

  const openCollapsedSearch = async () => {
    // 折叠态：仅展示搜索下拉面板，不展开侧栏
    if (!props.collapsed) return;
    isCollapsedSearchOpen.value = true;
    await nextTick();
    updateCollapsedSearchPanelPosition();
    collapsedSearchInputRef.value?.focus?.();
  };

  const closeCollapsedSearch = () => {
    isCollapsedSearchOpen.value = false;
  };

  watch(
    () => props.collapsed,
    (newVal) => {
      if (!newVal) closeCollapsedSearch();
    },
  );

  let documentMouseDownHandler: ((e: MouseEvent) => void) | null = null;
  let documentKeydownHandler: ((e: KeyboardEvent) => void) | null = null;

  watch(isCollapsedSearchOpen, (open) => {
    if (open) {
      documentMouseDownHandler = (e: MouseEvent) => {
        const rootEl = sidebarRootRef.value;
        if (!rootEl) return;
        if (!rootEl.contains(e.target as Node)) closeCollapsedSearch();
      };
      documentKeydownHandler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') closeCollapsedSearch();
      };
      document.addEventListener('mousedown', documentMouseDownHandler);
      window.addEventListener('keydown', documentKeydownHandler);
      return;
    }

    if (documentMouseDownHandler) document.removeEventListener('mousedown', documentMouseDownHandler);
    if (documentKeydownHandler) window.removeEventListener('keydown', documentKeydownHandler);
    documentMouseDownHandler = null;
    documentKeydownHandler = null;
  });

  onUnmounted(() => {
    if (documentMouseDownHandler) document.removeEventListener('mousedown', documentMouseDownHandler);
    if (documentKeydownHandler) window.removeEventListener('keydown', documentKeydownHandler);
  });

  const collapsedSortedConversations = computed(() => {
    const pinned = props.conversations.filter(c => c.pinned);
    const unpinned = props.conversations.filter(c => !c.pinned);
    return [...pinned, ...unpinned];
  });

  const collapsedFilteredHistoryList = computed(() => {
    const keyword = collapsedSearchKeyword.value.trim();
    if (!keyword) return collapsedSortedConversations.value;
    return collapsedSortedConversations.value.filter(c => c.title.includes(keyword));
  });

  const escapeHtml = (str: string) => str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const getHighlightedTitle = (title: string) => {
    const keyword = collapsedSearchKeyword.value.trim();
    if (!keyword) return escapeHtml(title);
    if (!title.includes(keyword)) return escapeHtml(title);

    const parts = title.split(keyword);
    if (parts.length === 1) return escapeHtml(title);

    // 用 v-html 包裹高亮，确保未匹配部分已做转义，避免 XSS
    return parts
      .map((p, idx) => {
        const safeText = escapeHtml(p);
        if (idx === parts.length - 1) return safeText;
        return `${safeText}<span class="search-highlight">${escapeHtml(keyword)}</span>`;
      })
      .join('');
  };

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
    closeSidebarPopovers();
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

  const filteredHistoryList = computed(() => {
    const ungrouped = props.conversations.filter(c => !c.groupName);
    const sorted = [
      ...ungrouped.filter(c => c.pinned),
      ...ungrouped.filter(c => !c.pinned),
    ];
    if (!searchKeyword.value) return sorted;
    return sorted.filter(c => c.title.includes(searchKeyword.value));
  });

  const filteredGroupedHistory = computed(() => {
    const grouped: Record<string, Conversation[]> = {};
    // Initialize all groups
    props.groups.forEach((g) => {
      grouped[g.name] = [];
    });
    const groupedConvs = props.conversations.filter(c => c.groupName);
    for (const conv of groupedConvs) {
      if (searchKeyword.value && !conv.title.includes(searchKeyword.value)) continue;
      const key = conv.groupName!;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(conv);
    }
    return grouped;
  });

  // 分组折叠状态（默认折叠空分组与无展开项）
  const collapsedGroups = ref<Set<string>>(new Set(['风险分析', '风险解读']));

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

  // 新建分组气泡弹窗
  const addGroupDialog = ref({
    show: false,
    name: '',
  });
  const addGroupInputRef = ref<any>(null);

  const closeAddGroupPopover = () => {
    addGroupDialog.value.show = false;
    addGroupDialog.value.name = '';
  };

  const onAddGroupShowChange = (val: boolean) => {
    addGroupDialog.value.show = val;
    if (!val) addGroupDialog.value.name = '';
  };

  const handleAddGroupPopoverShow = async () => {
    addGroupDialog.value.name = '';
    await nextTick();
    const inputRef = addGroupInputRef.value;
    if (typeof inputRef?.focus === 'function') {
      inputRef.focus();
      return;
    }
    inputRef?.$el?.querySelector?.('input')?.focus();
  };

  const confirmAddGroup = () => {
    const groupName = addGroupDialog.value.name.trim();
    if (!groupName) return;
    const newGroups = [...props.groups, { id: `g_${Date.now()}`, name: groupName }];
    emit('update-groups', newGroups);
    closeAddGroupPopover();
  };

  // 重命名分组
  const editingGroup = ref<string | null>(null);
  const editGroupName = ref('');
  const editGroupInputRef = ref<HTMLInputElement | null>(null);

  const ignoreEditGroupBlur = ref(false);

  const startEditGroup = async (groupName: string) => {
    ignoreEditGroupBlur.value = true;
    editingGroup.value = groupName;
    editGroupName.value = groupName;
    hideGroupMenu();
    await nextTick();
    editGroupInputRef.value?.focus?.();
    window.setTimeout(() => {
      editGroupInputRef.value?.focus?.();
      ignoreEditGroupBlur.value = false;
    }, 50);
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
    if (ignoreEditGroupBlur.value) return;
    editingGroup.value = null;
  };

  // 重命名会话
  const editingConvId = ref<string | null>(null);
  const editConvTitle = ref('');
  const editConvInputRef = ref<any>(null);

  const ignoreEditConvBlur = ref(false);

  const getEditConvInputEl = () => {
    const inputRef = Array.isArray(editConvInputRef.value)
      ? editConvInputRef.value[0]
      : editConvInputRef.value;
    if (!inputRef) return null;
    if (typeof inputRef.focus === 'function' && inputRef.$el) {
      return inputRef.$el.querySelector?.('input') as HTMLInputElement | null;
    }
    if (inputRef instanceof HTMLInputElement) return inputRef;
    return inputRef;
  };

  const startEditConv = async (id: string, title: string) => {
    ignoreEditConvBlur.value = true;
    hideMenu();
    editingConvId.value = id;
    editConvTitle.value = title;
    await nextTick();
    const nativeInput = getEditConvInputEl();
    nativeInput?.focus?.();
    window.setTimeout(() => {
      getEditConvInputEl()?.focus?.();
      ignoreEditConvBlur.value = false;
    }, 50);
  };

  const confirmEditConv = (id: string) => {
    const newTitle = editConvTitle.value.trim();
    if (newTitle) {
      emit('update-conv-title', id, newTitle);
    }
    editingConvId.value = null;
  };

  const cancelEditConv = () => {
    if (ignoreEditConvBlur.value) return;
    editingConvId.value = null;
  };

  // 删除分组确认弹窗：复用之前的删除 InfoBox 风格
  const showDeleteGroup = (groupName: string) => {
    hideGroupMenu();

    const confirmName = ref('');
    const confirmBtnClass = 'chat-delete-group-confirm-btn';
    const groupConversationsCount = props.conversations.filter(c => c.groupName === groupName).length;

    const getConfirmBtnStyle = (isMatch: boolean) => ({
      height: '32px',
      padding: '0 16px',
      fontSize: '14px',
      lineHeight: '32px',
      borderRadius: '2px',
      border: '1px solid',
      outline: 'none',
      marginRight: '8px',
      backgroundColor: isMatch ? '#ea3636' : '#fff',
      borderColor: isMatch ? '#ea3636' : '#dcdee5',
      color: isMatch ? '#fff' : '#c4c6cc',
      cursor: isMatch ? 'pointer' : 'not-allowed',
    });

    const cancelBtnStyle = {
      height: '32px',
      padding: '0 16px',
      fontSize: '14px',
      lineHeight: '32px',
      borderRadius: '2px',
      border: '1px solid #c4c6cc',
      outline: 'none',
      marginRight: '0',
      backgroundColor: '#fff',
      color: '#63656e',
      cursor: 'pointer',
    };

    const infoBoxInputStyle = {
      width: '100%',
      height: '32px',
      padding: '0 10px',
      fontSize: '14px',
      border: '1px solid #c4c6cc',
      borderRadius: '2px',
      outline: 'none',
      boxSizing: 'border-box',
    };

    const updateConfirmBtn = (isMatch: boolean) => {
      const btn = document.querySelector(`.${confirmBtnClass}`) as HTMLButtonElement | null;
      if (!btn) return;
      if (isMatch) {
        btn.removeAttribute('disabled');
      } else {
        btn.setAttribute('disabled', 'disabled');
      }
      Object.assign(btn.style, getConfirmBtnStyle(isMatch));
    };

    const copyGroupName = () => {
      if (!groupName) return;
      navigator.clipboard.writeText(groupName)
        .then(() => messageSuccess('复制成功'))
        .catch(() => undefined);
    };

    const deleteInfoInstance = InfoBox({
      type: 'warning',
      title: '确定删除该分组？',
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      subTitle: () => h('div', { style: { textAlign: 'left' } }, [
        h('div', {
          style: {
            padding: '12px 16px',
            marginBottom: '16px',
            lineHeight: '22px',
            backgroundColor: '#f5f7fa',
            borderRadius: '2px',
            fontSize: '14px',
            color: '#63656e',
          },
        }, [
          '删除分组将',
          h('span', { style: { fontWeight: 600, color: '#ea3636' } }, '同步删除该分组下的'),
          ' ',
          h('span', { style: { fontWeight: 700, color: '#ea3636' } }, `${groupConversationsCount}`),
          ' ',
          h('span', { style: { fontWeight: 600, color: '#ea3636' } }, '个会话'),
          '，请谨慎操作！',
        ]),
        h('div', {
          style: { marginBottom: '8px', fontSize: '14px', color: '#63656e' },
        }, [
          h('span', {}, '请输入分组名称「'),
          h('span', {
            style: { fontWeight: 600, color: '#313238', cursor: 'pointer' },
            onClick: copyGroupName,
          }, groupName),
          h('span', {}, '」以继续'),
        ]),
        h('input', {
          value: confirmName.value,
          placeholder: `请输入分组名称：${groupName}`,
          onInput: (e: Event) => {
            const { value } = e.target as HTMLInputElement;
            confirmName.value = value;
            updateConfirmBtn(value.trim() === groupName);
          },
          style: infoBoxInputStyle,
        }),
      ]),
      footer: () => h('div', {
        style: {
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        },
      }, [
        h('button', {
          class: `info-box-confirm-btn ${confirmBtnClass}`,
          onClick: () => {
            if (confirmName.value.trim() !== groupName) return;
            // 不提供同步删除选项：按设计直接删除分组下的会话
            emit('delete-group', groupName, false);
            deleteInfoInstance?.hide();
          },
          onVnodeMounted: (vnode: any) => {
            const el = vnode.el as HTMLButtonElement;
            el.setAttribute('disabled', 'disabled');
            Object.assign(el.style, getConfirmBtnStyle(false));
          },
        }, '删除'),
        h('button', {
          style: cancelBtnStyle,
          onClick: () => deleteInfoInstance?.hide(),
        }, '取消'),
      ]),
      onClose() {
        confirmName.value = '';
        // InfoBox 的 DOM 可能复用/未销毁；关闭时强制重置按钮，避免“关掉后仍可点击”。
        const btn = document.querySelector(`.${confirmBtnClass}`) as HTMLButtonElement | null;
        if (btn) {
          btn.setAttribute('disabled', 'disabled');
          Object.assign(btn.style, getConfirmBtnStyle(false));
        }
      },
    });
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

  const handleDelete = (conv: Conversation) => {
    hideMenu();
    showDeleteConversationDialog(conv);
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

  const showExportDialog = (type: string, ids?: string[]) => {
    exportDialog.value.type = type;
    exportDialog.value.selectedIds = ids ? [...ids] : [];
    exportDialog.value.show = true;
    closeSidebarPopovers();
    hideMenu();
    hideGroupMenu();
  };

  const showGroupExportDialog = (type: string, groupName: string) => {
    const ids = props.conversations
      .filter(c => c.groupName === groupName)
      .map(c => c.id);
    showExportDialog(type, ids);
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
    closeSidebarPopovers();
  };

  watch(
    () => [exportDialog.value.show, importDialog.value.show],
    ([exportShow, importShow]) => {
      if (exportShow || importShow) {
        nextTick(() => {
          closeSidebarPopovers();
        });
      }
    },
  );

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

  // 删除会话 / 清空所有会话：复用场景配置/平台管理删除弹窗（InfoBox）
  const CLEAR_CONFIRM_TEXT = '确认清空';

  const getDangerConfirmBtnStyle = (isMatch: boolean) => ({
    height: '32px',
    padding: '0 16px',
    fontSize: '14px',
    lineHeight: '32px',
    borderRadius: '2px',
    border: '1px solid',
    outline: 'none',
    marginRight: '8px',
    backgroundColor: isMatch ? '#ea3636' : '#fff',
    borderColor: isMatch ? '#ea3636' : '#dcdee5',
    color: isMatch ? '#fff' : '#c4c6cc',
    cursor: isMatch ? 'pointer' : 'not-allowed',
  });

  const infoBoxCancelBtnStyle = {
    height: '32px',
    padding: '0 16px',
    fontSize: '14px',
    lineHeight: '32px',
    borderRadius: '2px',
    border: '1px solid #c4c6cc',
    outline: 'none',
    marginRight: '0',
    backgroundColor: '#fff',
    color: '#63656e',
    cursor: 'pointer',
  };

  const infoBoxInputStyle = {
    width: '100%',
    height: '32px',
    padding: '0 10px',
    fontSize: '14px',
    border: '1px solid #c4c6cc',
    borderRadius: '2px',
    outline: 'none',
    boxSizing: 'border-box',
  };

  const updateDangerConfirmBtn = (className: string, isMatch: boolean) => {
    const btn = document.querySelector(`.${className}`) as HTMLButtonElement | null;
    if (!btn) return;
    if (isMatch) {
      btn.removeAttribute('disabled');
    } else {
      btn.setAttribute('disabled', 'disabled');
    }
    Object.assign(btn.style, getDangerConfirmBtnStyle(isMatch));
  };

  const copyConfirmName = (name: string) => {
    if (!name) return;
    navigator.clipboard.writeText(name).then(() => {
      messageSuccess('复制成功');
    });
  };

  const showDeleteConversationDialog = (conv: Conversation) => {
    const confirmName = ref('');
    const confirmBtnClass = 'chat-delete-confirm-btn';
    const deleteInfoInstance = InfoBox({
      type: 'warning',
      title: '确定删除该会话？',
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      subTitle: () => h('div', { style: { textAlign: 'left' } }, [
        h('div', {
          style: {
            padding: '12px 16px',
            marginBottom: '16px',
            fontSize: '14px',
            lineHeight: '22px',
            color: '#63656e',
            textAlign: 'left',
            backgroundColor: '#f5f7fa',
            borderRadius: '2px',
          },
        }, [
          '此操作将',
          h('span', { style: { fontWeight: 600, color: '#ea3636' } }, '永久删除该会话及消息记录'),
          '，不可恢复，请谨慎操作！',
        ]),
        h('div', {
          style: {
            marginBottom: '8px',
            fontSize: '14px',
            color: '#63656e',
          },
        }, [
          '请输入会话名称「',
          h('span', {
            style: { fontWeight: 600, color: '#313238', cursor: 'pointer' },
            onClick: () => copyConfirmName(conv.title),
          }, conv.title),
          '」以确认删除',
        ]),
        h('input', {
          value: confirmName.value,
          placeholder: '请输入待删除的会话名称',
          onInput: (e: Event) => {
            const { value } = e.target as HTMLInputElement;
            confirmName.value = value;
            updateDangerConfirmBtn(confirmBtnClass, value.trim() === conv.title);
          },
          style: infoBoxInputStyle,
        }),
      ]),
      footer: () => h('div', {
        style: {
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        },
      }, [
        h('button', {
          class: `info-box-confirm-btn ${confirmBtnClass}`,
          onClick: () => {
            if (confirmName.value.trim() !== conv.title) return;
            emit('delete', conv.id);
            deleteInfoInstance.hide();
          },
          onVnodeMounted: (vnode: any) => {
            const el = vnode.el as HTMLButtonElement;
            el.setAttribute('disabled', 'disabled');
            Object.assign(el.style, getDangerConfirmBtnStyle(false));
          },
        }, '删除'),
        h('button', {
          style: infoBoxCancelBtnStyle,
          onClick: () => deleteInfoInstance.hide(),
        }, '取消'),
      ]),
      onClose() {
        confirmName.value = '';
        // InfoBox 的 DOM 可能复用/未销毁；关闭时强制重置按钮，避免“关掉后仍可点击”。
        const btn = document.querySelector(`.${confirmBtnClass}`) as HTMLButtonElement | null;
        if (btn) {
          btn.setAttribute('disabled', 'disabled');
          Object.assign(btn.style, getDangerConfirmBtnStyle(false));
        }
      },
    });
  };

  const showClearAllDialog = () => {
    closeSidebarPopovers();
    const confirmText = ref('');
    const clearInfoInstance = InfoBox({
      type: 'warning',
      title: '确定清空所有会话？',
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      subTitle: () => h('div', { style: { textAlign: 'left' } }, [
        h('div', {
          style: {
            padding: '12px 16px',
            marginBottom: '16px',
            fontSize: '14px',
            lineHeight: '22px',
            color: '#63656e',
            textAlign: 'left',
            backgroundColor: '#f5f7fa',
            borderRadius: '2px',
          },
        }, [
          '此操作将删除所有会话及消息记录，包括已分组和未分组的共 ',
          h('strong', {}, String(props.conversations.length)),
          ' 个会话。',
          h('br'),
          h('span', { style: { fontWeight: 600, color: '#ea3636' } }, '此操作不可恢复，请谨慎操作！'),
        ]),
        h('div', {
          style: {
            marginBottom: '8px',
            fontSize: '14px',
            color: '#63656e',
          },
        }, '请输入「确认清空」以继续'),
        h('input', {
          value: confirmText.value,
          placeholder: CLEAR_CONFIRM_TEXT,
          onInput: (e: Event) => {
            const { value } = e.target as HTMLInputElement;
            confirmText.value = value;
            updateDangerConfirmBtn('chat-clear-confirm-btn', value === CLEAR_CONFIRM_TEXT);
          },
          style: infoBoxInputStyle,
        }),
      ]),
      footer: () => h('div', {
        style: {
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        },
      }, [
        h('button', {
          class: 'info-box-confirm-btn chat-clear-confirm-btn',
          style: getDangerConfirmBtnStyle(false),
          onClick: () => {
            if (confirmText.value !== CLEAR_CONFIRM_TEXT) return;
            emit('clear-all');
            clearInfoInstance.hide();
          },
        }, '清空'),
        h('button', {
          style: infoBoxCancelBtnStyle,
          onClick: () => clearInfoInstance.hide(),
        }, '取消'),
      ]),
      onClose() {
        confirmText.value = '';
      },
    });
  };
</script>

<style
  lang="postcss"
  src="./chat-sidebar.css" />
