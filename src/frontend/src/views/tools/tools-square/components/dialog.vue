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
  <bk-dialog
    ref="dialogRef"
    class="tools-use-dialog"
    draggable
    :esc-close="false"
    :fullscreen="isFullScreen"
    :is-show="isShow"
    render-directive="show"
    :show-mask="false"
    :style="{
      'z-index': dialogIndex,
      'position': 'absolute'
    }"
    :width="dialogWidth"
    :z-index="dialogIndex"
    @click="handleClick"
    @closed="handleCloseDialog">
    <template #header>
      <div
        v-if="isShowTags"
        class="dialog-tool">
        <dialog-header
          ref="dialogHeaderRef"
          :tabs="tabs"
          @click-item="handleClickTag" />
      </div>
      <div
        class="header"
        :style="`margin-top: ${isShowTags ? '10px' : '24px'};`">
        <div class="header-left">
          <audit-icon
            class="full-screen-img"
            svg
            :type="isFullScreen ? 'un-full-screen-2' : 'full-screen'"
            @click="handleFullscreen()" />
        </div>
        <div class="top-right">
          <audit-icon
            class="top-left-icon"
            svg
            :type="toolDetails ? itemIcon(toolDetails) : ''" />
          <div class="top-right-box">
            <div class="top-right-title">
              <tool-tips
                class="top-right-name"
                :data="toolDetails?.name || ''" />
              <bk-tag
                v-for="(tag, tagIndex) in toolDetails?.tags?.slice(0, 3)"
                :key="tagIndex"
                class="desc-tag">
                {{ returnTagsName(tag) }}
              </bk-tag>
              <bk-tag
                v-if="toolDetails?.tags && toolDetails.tags.length > 3"
                v-bk-tooltips="{
                  content: tagContent(toolDetails.tags),
                  placement: 'top',
                }"
                class="desc-tag">
                + {{ toolDetails.tags.length - 3
                }}
              </bk-tag>
              <bk-tag
                class="desc-tag desc-tag-info"
                theme="info"
                @click="handlesStrategiesClick(toolDetails)">
                {{ t('运用在') }} {{ toolDetails?.strategies?.length }} {{ t('个策略中') }}
              </bk-tag>
            </div>
            <div class="top-right-desc">
              {{ toolDetails?.description }}
            </div>
          </div>
        </div>
      </div>
    </template>
    <template #default>
      <div class="top-line" />
      <div
        id="scroll-dialog-content"
        :style="{ height: dialogHeight }">
        <scroll-faker>
          <template
            v-if="toolDetails?.tool_type === 'data_search' || toolDetails?.tool_type === 'api'">
            <div v-if="toolDetails?.permission.use_tool">
              <div class="top-search">
                <div class="top-search-title">
                  {{ t('查询输入') }}
                </div>
                <bk-form
                  ref="formRef"
                  class="example"
                  form-type="vertical"
                  :model="searchFormData"
                  :rules="rules">
                  <div class="formref-item">
                    <bk-form-item
                      v-for="(item, index) in searchList"
                      :key="index"
                      class="formref-item-item"
                      :label="item?.display_name"
                      :property="item?.raw_name"
                      :required="item?.required">
                      <template #label>
                        <span
                          v-bk-tooltips="{
                            disabled: item?.description === '',
                            content: item?.description,
                          }">
                          {{ item?.display_name }}
                        </span>
                      </template>
                      <form-item
                        ref="formItemRef"
                        :data-config="item"
                        @change="(val:any) => handleFormItemChange(val, item)" />
                    </bk-form-item>
                  </div>
                </bk-form>
                <div v-if="source === ''">
                  <bk-button
                    class="mr8"
                    theme="primary"
                    @click.stop="submit">
                    查询
                  </bk-button>
                  <bk-button
                    class="mr8"
                    @click.stop="handleReset">
                    重置
                  </bk-button>
                </div>
              </div>
              <div class="top-search">
                <div class="top-search-title">
                  {{ t('查询结果') }}
                </div>
                <div class="top-search-result">
                  <bk-loading :loading="isLoading">
                    <!-- sql工具 -->
                    <template v-if="toolDetails?.tool_type === 'data_search'">
                      <bk-table
                        :border="['row','outer','col']"
                        :columns="columns"
                        :data="tableData"
                        header-align="center"
                        :max-height="dialogTableHeight"
                        :pagination="pagination"
                        remote-pagination
                        show-overflow-tooltip
                        @page-limit-change="handlePageLimitChange"
                        @page-value-change="handlePageChange" />
                    </template>

                    <!-- api工具 -->
                    <template v-if="toolDetails?.tool_type === 'api'">
                      <template v-if="apiDataStatus === 200 && groupData.length > 0">
                        <bk-card
                          v-for="(group, groupIndex) in groupData"
                          :key="groupIndex"
                          is-collapse
                          :title="t(`分组${groupIndex + 1}`)">
                          <div class="card-content">
                            <!-- KV 字段展示 -->
                            <template v-if="group.kv_fields && group.kv_fields.length > 0">
                              <render-info-block
                                v-for="(kvFieldsChunk, chunkIndex) in chunkArray(group.kv_fields, 3)"
                                :key="chunkIndex"
                                style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                                <render-info-item
                                  v-for="(kvField, kvIndex) in kvFieldsChunk"
                                  :key="kvIndex"
                                  class="kv-field-item"
                                  :label="kvField.display_name || kvField.raw_name">
                                  <template v-if="getMappedValue(kvField) || hasDrillConfig(kvField)">
                                    <!-- 有字段映射或者有证据下探 -->
                                    <div style="display: flex; align-items: center; gap: 5px;">
                                      <bk-popover
                                        placement="top"
                                        theme="black">
                                        <span
                                          :class="[
                                            getMappedValue(kvField) ? 'tips' : '',
                                          ]"
                                          :style="{
                                            color: hasDrillConfig(kvField) ? '#3a84ff' : '#313238',
                                            cursor: hasDrillConfig(kvField) ? 'pointer' : 'default',
                                          }"
                                          @click.stop="hasDrillConfig(kvField) && handleKVFieldDownClick(kvField)">
                                          {{ getMappedValue(kvField)?.name || kvField.resolvePathValue }}
                                        </span>
                                        <template #content>
                                          <div>
                                            <div v-if="getMappedValue(kvField)">
                                              <span>{{ t('存储值: ') }}</span>
                                              <span>{{ getMappedValue(kvField)?.key }}</span>
                                              <br>
                                              <span>{{ t('展示文本: ') }}</span>
                                              <span>{{ getMappedValue(kvField)?.name }}</span>
                                            </div>
                                            <div
                                              v-if="hasDrillConfig(kvField)"
                                              :style="{
                                                marginTop: getMappedValue(kvField) ? '8px' : '0',
                                              }">
                                              {{ t('点击查看此字段的证据下探') }}
                                            </div>
                                          </div>
                                        </template>
                                      </bk-popover>
                                      <!-- 证据下探按钮 -->
                                      <bk-popover
                                        v-if="hasDrillConfig(kvField)"
                                        placement="top"
                                        theme="black">
                                        <template #content>
                                          <div>
                                            <div
                                              v-for="config in kvField.drill_config"
                                              :key="config.tool.uid">
                                              {{ config.drill_name || getToolNameAndType(config.tool.uid).name }}
                                              <bk-button
                                                class="ml8"
                                                text
                                                theme="primary"
                                                @click.stop="handleKVFieldDownClick(kvField, config.tool.uid)">
                                                {{ t('去查看') }}
                                                <audit-icon
                                                  class="mr-18"
                                                  type="jump-link" />
                                              </bk-button>
                                            </div>
                                          </div>
                                        </template>
                                        <span
                                          :style="{
                                            padding: '1px 8px',
                                            backgroundColor: '#cddffe',
                                            borderRadius: '8px',
                                            color: '#3a84ff',
                                            cursor: 'pointer',
                                          }"
                                          @click.stop="handleKVFieldDownClick(kvField)">
                                          {{ kvField.drill_config.length }}
                                        </span>
                                      </bk-popover>
                                    </div>
                                  </template>
                                  <!-- 没有字段映射或者没有证据下探 -->
                                  <span v-else>
                                    {{ kvField.resolvePathValue }}
                                  </span>
                                </render-info-item>
                              </render-info-block>
                            </template>
                            <!-- Table 字段展示 -->
                            <template
                              v-for="(tableField, tableIndex) in group.table_fields"
                              :key="tableIndex">
                              <div class="top-search-table-title">
                                {{ tableField.display_name || tableField.raw_name }}
                              </div>
                              <bk-table
                                :border="['row','outer','col']"
                                :columns="tableField.columns"
                                :data="tableField.tableData"
                                header-align="center"
                                :max-height="dialogTableHeight"
                                :pagination="tableField.pagination"
                                show-overflow-tooltip
                                @page-limit-change="(val: number) => {
                                  handleGroupTablePageLimitChange(groupIndex, tableIndex, val);
                                }"
                                @page-value-change="(val: number) => {
                                  handleGroupTablePageChange(groupIndex, tableIndex, val);
                                }" />
                            </template>
                          </div>
                        </bk-card>
                      </template>
                      <template v-else>
                        <bk-exception
                          :description="t('请联系工具维护人员进行修复')"
                          :title="t('数据查询失败')"
                          type="500">
                          <div>
                            <a
                              href=""
                              target="_blank">
                              <audit-icon
                                style="margin-right: 6px;"
                                type="qw" />
                              <span>{{ toolDetails.created_by }}、{{ toolDetails.updated_by }}</span>
                            </a>
                          </div>
                        </bk-exception>
                      </template>
                    </template>
                  </bk-loading>
                </div>
              </div>
            </div>
            <div
              v-else
              class="default-permission">
              <div class="no-permission">
                <img
                  class="no-permission-img"
                  src="@images/no-permission.svg">
                <div class="no-permission-desc">
                  <p class="no-permission-title">
                    {{ t('无使用权限') }}
                  </p>
                  <p class="no-permission-text">
                    {{ t('你没有该工具的使用权限，请前往申请权限') }}
                  </p>
                  <p
                    class="no-permission-btn"
                    @click.stop="handleIamApply">
                    {{ t('申请权限') }}
                  </p>
                </div>
              </div>
            </div>
          </template>

          <!-- bkVision工具 -->
          <template
            v-else>
            <div
              :id="`panel-${uid}`"
              ref="panelRef"
              class="panel" />
          </template>
        </scroll-faker>
      </div>

      <div
        v-if="!isFullScreen"
        class="resize-handle"
        @mousedown="startResize" />
      <div
        v-if="!isFullScreen"
        class="resize-handle-left"
        @mousedown="startResizeLeft" />
    </template>
    <template #footer>
      <!-- <div
        v-if="!isFullScreen"
        class="resize-handle-top"
        @mousedown="startResizeBottom" /> -->
    </template>
  </bk-dialog>
</template>
<script setup lang='tsx'>
  import _ from 'lodash';
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import ToolManageService from '@service/tool-manage';

  import IamApplyDataModel from '@model/iam/apply-data';
  import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useMessage from '@hooks/use-message';

  import ToolTips from '@components/show-tooltips-text/index.vue';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import RenderInfoItem from '@views/strategy-manage/list/components/render-info-item.vue';

  import DialogHeader from './dialog-header.vue';

  import useEventBus from '@/hooks/use-event-bus';
  import useRequest from '@/hooks/use-request';
  import FormItem from '@/views/tools/tools-square/components/form-item.vue';

  interface Error {
    data: Record<string, any>,
    message: string,
    status: number
  }
  interface Column {
    label: string;
    field: string;
    width?: number;
    minWidth?: number;
    sortable?: boolean;
    showOverflowTooltip?: boolean;
  }
  interface TagItem {
    tag_id: string
    tag_name: string
    tool_count: number
    icon?: string;
  }
  interface SearchItem {
    value: any;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
    choices:Array<{
      key: string,
      name: string
    }>;
    disabled: boolean;
  }
  interface Props {
    tagsEnums: Array<TagItem>,
    source?: string,
    allToolsData: Array<ToolDetailModel>,
  }
  interface DrillDownItem {
    raw_name: string;
    display_name: string;
    description: string;
    drill_config: Array<{
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
        target_field_type?: string;
      }>;
      drill_name?: string;
    }>;
    enum_mappings: {
      collection_id: string;
      mappings: Array<{
        key: string;
        name: string;
      }>;
    };
  }
  interface TableDataItem {
    [key: string]: any;
  }

  interface tabsItem {
    uid: string;
    name: string;
  }

  // API工具分组表格配置
  interface GroupTableConfig {
    kv_fields: Array<{
      drill_config: DrillDownItem['drill_config'];
      enum_mappings: DrillDownItem['enum_mappings'];
      raw_name: string;
      display_name: string;
      description: string;
      path: string;
      resolvePathValue: unknown;
    }>;
    table_fields: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      path: string;
      columns: Column[];
      tableData: TableDataItem[];
      pagination: {
        count: number;
        limit: number;
        current: number;
        limitList: number[];
      };
    }>;
  }

  interface Exposes {
    closeDialog: () => void,
    openDialog: (
      itemUid: string,  // 工具信息
      drillDownItem?: DrillDownItem, // 下钻信息
      drillDownItemRowData?: Record<string, string>, // 下钻table所在行信息
      activeUid?: string, // 多工具时，当前激活的工具信息
      isRiskToolParams?: Record<string, any>, // 风险工具参数
      preview?: boolean // 是否预览
    ) => void,
    initTabsValue: (tabs: Array<tabsItem>, id: string) => void;
  }
  interface Emits {
    (e: 'openFieldDown', drillDownItem: DrillDownItem, drillDownItemRowData: Record<string, any>, activeUid?: string): void;
    (e: 'close', val?: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    source: '',
    isShowTags: false, // 是否显示标签
  });
  const emit = defineEmits<Emits>();
  const   emitBus  = useEventBus().emit;
  const { messageError } = useMessage();
  const { t } = useI18n();

  const dialogHeaderRef = ref();
  const dialogIndex = ref(3000);
  const dialogWidth = ref('50%');
  const dialogHeight = ref('50vh');
  const dialogTableHeight = ref('300px');
  const isFullScreen = ref(false);
  const isLoading = ref(false);
  const isShow = ref(false);
  const isPreview = ref<boolean | undefined>(false);
  const isDrillDownOpen = ref(false);
  const formItemRef = ref();

  const searchList = ref<SearchItem[]>([]);
  const tableData = ref<TableDataItem[]>([]);
  const columns = ref<Column[]>([]);
  const pagination = ref({
    count: 0,
    limit: 100,
    current: 1,
    limitList: [100, 200, 500, 1000],
  });

  const groupData = ref<GroupTableConfig[]>([]);
  const apiDataStatus = ref<number>(200);

  const uid = ref('');
  const panelId = ref('');
  const rules = ref({});
  const formRef = ref();
  const searchFormData = ref();
  const router = useRouter();
  const tabs = ref<Array<tabsItem>>([]);
  const drillDownItemConfig = ref<DrillDownItem['drill_config'][0]['config']>([]);
  const drillDownItemRowData = ref<Record<string, any>>({});
  const drillDownItem = ref<DrillDownItem>();
  // 权限
  const urlIamApply = ref('');
  const riskToolParams = ref<Record<string, any> | undefined>(undefined);
  const dialogUid = ref('');
  const isShowTags = ref(false);

  // 当前激活的工具
  const activeUid = ref('');

  // 工具执行
  const {
    run: fetchToolsExecute,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      if (data === undefined) {
        tableData.value = [];
      }
      if (toolDetails.value?.tool_type === 'data_search') {
        tableData.value = data.data.results;
        pagination.value.count = data.data.total;
      }
      console.log('execute data:', data);

      apiDataStatus.value = data.data.status_code;
      if (toolDetails.value?.tool_type === 'api' && apiDataStatus.value === 200) {
        const { result } = data.data;
        // 更新每个 group 的 table_fields 数据
        groupData.value = groupData.value.map(group => ({
          ...group,
          kv_fields: group.kv_fields.map(kvField => ({
            ...kvField,
            resolvePathValue: extractDataByPath(result, kvField.path),
          })),
          table_fields: group.table_fields.map((tableField) => {
            // 根据 path (json_path) 从 data 中提取对应的表格数据
            const tableData = extractDataByPath(result, tableField.path);
            let finalTableData: any[] = [];
            let count = 0;
            if (Array.isArray(tableData)) {
              finalTableData = tableData;
              count = tableData.length;
            } else if (tableData) {
              finalTableData = [tableData];
              count = 1;
            }
            return {
              ...tableField,
              tableData: Array(100).fill(finalTableData[0]),
              pagination: {
                ...tableField.pagination,
                count,
              },
            };
          }),
        }));
      }
      panelId.value = data.data.panel_id;
      initBK(data.data.panel_id);
    },
  });

  // 获取表格数据的方法
  const fetchTableData = () => {
    isLoading.value = true;
    fetchToolsExecute({
      uid: uid.value,
      params: {
        tool_variables: searchList.value.map(item => ({
          raw_name: item.raw_name,
          // eslint-disable-next-line no-nested-ternary
          value: (item.field_category === 'person_select') ? (item.value.length === 0 ?  '' :  item.value.join(','))  :  item.value,
        })),
        page: pagination.value.current,
        page_size: pagination.value.limit,
      },
      ...(riskToolParams.value && Object.keys(riskToolParams.value).length > 0 ? riskToolParams.value : {}),
    })
      .finally(() => {
        isLoading.value = false;
      });
  };

  // 获取工具详情
  const {
    run: fetchToolsDetail,
    data: toolDetails,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      uid.value = data.uid;

      // 权限
      if (!data?.permission.use_tool) {
        getApplyData({
          action_ids: 'use_tool',
          resources: data.uid,
        });
      }

      // 预览 （暂时用不上）
      /* if (isPreview.value) {
        const detail = new ToolDetailModel();
        createDialogContent({
          ...detail,
          ...res,
        } as ToolDetailModel);
        return;
      } */

      if (data.tool_type === 'bk_vision') {
        // bkVision直接请求
        fetchTableData();
      } else {
        // 创建弹框form、table
        createDialogContent(data);
      }

      setTimeout(() => {
        const modals = document.querySelectorAll('.tools-use-dialog .bk-modal-wrapper');

        // 遍历所有弹窗，只调整未被拖动过的弹窗位置
        Array.from(modals).reverse()
          .forEach((modal, index) => {
            const htmlModal = modal as HTMLElement;
            // 只调整未被拖动过的弹窗（没有transform样式）且不是第一个弹窗
            if (index > 0 && !htmlModal.style.transform) {
              htmlModal.style.left = `${50 - (index + 1) * 2}%`;
            }
          });
      }, 0);
    },
  });

  // 策略跳转
  const handlesStrategiesClick = (item: any) => {
    if (item?.strategies.length === 0) {
      return;
    }
    const url = router.resolve({
      name: 'strategyList',
      query: {
        strategy_id: item?.strategies.join(','),
      },
    }).href;
    window.open(url, '_blank');
  };

  const {
    run: getApplyData,
  } = useRequest(IamManageService.getApplyData, {
    defaultValue: new IamApplyDataModel(),
    onSuccess(result) {
      urlIamApply.value = result.apply_url;
    },
  });

  // 处理页码变化
  const handlePageChange = (newPage: number) => {
    pagination.value.current = newPage;
    fetchTableData(); // 调用获取表格数据的方法
  };

  // 处理每页条数变化
  const handlePageLimitChange = (newLimit: number) => {
    pagination.value.limit = newLimit;
    pagination.value.current = 1; // 重置到第一页
    fetchTableData(); // 调用获取表格数据的方法
  };

  // 将数组按指定大小分块
  const chunkArray = (array: any[], chunkSize: number): any[][] => {
    const chunks: any[][] = [];
    for (let i = 0; i < array.length; i += chunkSize) {
      chunks.push(array.slice(i, i + chunkSize));
    }
    return chunks;
  };

  // 根据 json_path 提取数据
  const extractDataByPath = (data: any, path: string): any => {
    if (!path || !data) return null;

    // 去掉路径中的下标，如 [1]、[26] 等
    const cleanPath = path.replace(/\[\d+\]/g, '');

    // 根据 . 分割路径，一层一层获取数据
    const pathParts = cleanPath.split('.').filter(part => part.length > 0);
    let result = data;

    for (const part of pathParts) {
      if (result === null || result === undefined) {
        return null;
      }
      result = result[part];
    }

    // 如果是字符串，去掉两边的引号（双引号或单引号）
    if (typeof result === 'string') {
      result = result.replace(/^["']|["']$/g, '');
    }

    return result;
  };

  // 处理分组表格页码变化
  const handleGroupTablePageChange = (groupIndex: number, tableIndex: number, newPage: number) => {
    if (groupData.value[groupIndex]?.table_fields[tableIndex]) {
      groupData.value[groupIndex].table_fields[tableIndex].pagination.current = newPage;
      fetchTableData();
    }
  };

  // 处理分组表格每页条数变化
  const handleGroupTablePageLimitChange = (groupIndex: number, tableIndex: number, newLimit: number) => {
    if (groupData.value[groupIndex]?.table_fields[tableIndex]) {
      groupData.value[groupIndex].table_fields[tableIndex].pagination.limit = newLimit;
      groupData.value[groupIndex].table_fields[tableIndex].pagination.current = 1; // 重置到第一页
      fetchTableData();
    }
  };


  // 标签名称
  const returnTagsName = (tags: string) => {
    let tagName = '';
    props.tagsEnums.forEach((item: TagItem) => {
      if (item.tag_id === tags) {
        tagName = item.tag_name;
      }
    });
    return tagName;
  };

  const tagContent = (tags: Array<string>) => {
    const tagNameList = props.tagsEnums.map((i:TagItem) => {
      if (tags.slice(3, tags.length).includes(i.tag_id)) {
        return i.tag_name;
      }
      return null;
    }).filter(e => e !== null);
    return tagNameList.join(',');
  };

  const getToolNameAndType = (uid: string) => {
    const tool = props.allToolsData?.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };

  const handleClick = () => {
    const isNewIndex = sessionStorage.getItem('dialogIndex');
    if (isNewIndex) {
      dialogIndex.value = Number(isNewIndex) + 1;
    } else {
      dialogIndex.value = dialogIndex.value + 1;
    }
    nextTick(() => {
      sessionStorage.setItem('dialogIndex', String(dialogIndex.value));
    });
  };

  const itemIcon = (item: ToolDetailModel) => {
    switch (item.tool_type) {
    case 'data_search':
      return 'sqlxiao';
    case 'bk_vision':
      return 'bkvisonxiao';
    case 'api':
      return 'apixiao';
    }
  };

  const handleIamApply = () => {
    window.open(urlIamApply.value, '_blank');
  };

  const submit = () => {
    searchList.value.forEach((item) => {
      searchFormData.value[item.raw_name] = item.value;
    });
    formRef.value.validate().then(() => {
      formItemRef.value && formItemRef.value.forEach((item: any) => {
        item?.getData();
      });
      fetchTableData();
    });
  };

  // 清空表单验证
  const handleReset = () => {
    pagination.value.current = 1;
    pagination.value.count = 0;
    pagination.value.limit = 100;
    tableData.value = [];
    isDrillDownOpen.value = false;
    drillDownItemConfig.value = [];
    drillDownItemRowData.value = {};

    // 检查 searchList.value 中的所有 value 是否为空
    const allValuesEmpty = searchList.value.every(item => item.value === null
      || (Array.isArray(item.value) && item.value.length === 0));
    if (allValuesEmpty) {
      return;
    }

    searchList.value = searchList.value.map(item => ({
      ...item,
      value: (item.field_category === 'person_select' || item.field_category === 'time_range_select') ? [] : null,
    }));

    if (formItemRef.value) {
      formItemRef.value.forEach((item: any) => {
        item?.resetValue();
      });
    }

    formRef.value.clearValidate();
  };

  const handleFormItemChange = (val: any, item: SearchItem) => {
    const target = searchList.value.find(i => i.raw_name === item.raw_name);
    if (target) {
      if (_.isEqual(target.value, val)) {
        return;
      }
      target.value = val;
    }

    searchFormData.value[item.raw_name] = val;
  };

  // 创建单元格渲染函数（公共函数）
  // eslint-disable-next-line max-len
  const createRenderCell = (fieldItem: OutputFields, toolData: ToolDetailModel) => ({ data }: { data: Record<any, any> }) => {
    const rawVal = data[fieldItem.raw_name];
    // 如果有enum映射，优先用映射的name
    const mappings = fieldItem.enum_mappings?.mappings;
    const mapped = Array.isArray(mappings) && mappings.length
      ? mappings.find((m: any) => String(m.key) === String(rawVal))
      : undefined;
    const display = mapped ? mapped.name : rawVal;
    if (fieldItem.drill_config === null
      || fieldItem.drill_config.length === 0
      || (fieldItem.drill_config.length === 1 && !fieldItem.drill_config[0].tool.uid)) {
      // 普通单元格
      return <span
          v-bk-tooltips={{
            content: t('映射对象', {
              key: mapped?.key,
              name: mapped?.name,
            }),
            disabled: !mapped,
          }}
          style={{
            cursor: 'pointer',
          }}
          class={{ tips: mapped }}
        >
          {display}
        </span>;
    }
    // 可下钻的列，显示按钮
    return (
        <div>
          <bk-popover
            placement="top"
            theme="black"
            v-slots={{
              content: () => (
                <>
                  {
                    mapped && (
                      <>
                        <span>
                          { t('存储值: ') }
                        </span>
                        <span>
                          { mapped?.key }
                        </span>
                        <br />
                        <span>
                          { t('展示文本: ') }
                        </span>
                        <span>
                          { mapped?.name }
                        </span>
                      </>
                    )
                  }
                  <div style={{
                    marginTop: '8px',
                  }}>
                    { t('点击查看此字段的证据下探') }
                  </div>
                </>
              ),
            }}>
            <span
              style={{
                cursor: 'pointer',
                color: '#3a84ff',
              }}
              class={{ tips: mapped }}
              onClick={(e: any) => {
                e.stopPropagation(); // 阻止事件冒泡
                handleFieldDownClick(fieldItem, toolData);
              }}>
              {display}
            </span>
          </bk-popover>
          <bk-popover
            placement="top"
            theme="black"
            v-slots={{
              content: () => (
                <div>
                  {fieldItem.drill_config.map(config => (
                    <div key={config.tool.uid}>
                      {config.drill_name || getToolNameAndType(config.tool.uid).name}
                      <bk-button
                        class="ml8"
                        theme="primary"
                        text
                        onClick={(e: any) => {
                          e.stopPropagation(); // 阻止事件冒泡
                          handleFieldDownClick(fieldItem, toolData, config.tool.uid);
                        }}>
                        {t('去查看')}
                        <audit-icon
                          class="mr-18"
                          type="jump-link" />
                      </bk-button>
                    </div>
                  ))}
                </div>
              ),
            }}>
            <span style={{
              padding: '1px 8px',
              backgroundColor: '#cddffe',
              borderRadius: '8px',
              marginLeft: '5px',
              color: '#3a84ff',
              cursor: 'pointer',
            }}
            onClick={(e: any) => {
              e.stopPropagation(); // 阻止事件冒泡
              handleFieldDownClick(fieldItem, toolData);
            }}>
              {fieldItem.drill_config.length}
            </span>
          </bk-popover>
        </div>
    );
  };

  // KV 字段辅助函数
  const getMappedValue = (kvField: GroupTableConfig['kv_fields'][0]) => {
    const rawVal = kvField.resolvePathValue;
    const mappings = kvField.enum_mappings?.mappings;
    if (Array.isArray(mappings) && mappings.length) {
      return mappings.find((m: any) => String(m.key) === String(rawVal));
    }
    return undefined;
  };

  const hasDrillConfig = (kvField: GroupTableConfig['kv_fields'][0]) => kvField.drill_config
    && Array.isArray(kvField.drill_config)
    && kvField.drill_config.length > 0
    && kvField.drill_config.some((config: any) => config.tool?.uid);

  const handleKVFieldDownClick = (kvField: GroupTableConfig['kv_fields'][0], activeUid?: string) => {
    const drillDownItem: DrillDownItem = {
      raw_name: kvField.raw_name,
      display_name: kvField.display_name,
      description: kvField.description,
      drill_config: kvField.drill_config as DrillDownItem['drill_config'],
      enum_mappings: kvField.enum_mappings,
    };
    handleFieldDownClick(drillDownItem, { [kvField.raw_name]: kvField.resolvePathValue }, activeUid);
  };

  // 创建弹窗内容
  const createDialogContent = (data: ToolDetailModel) => {
    console.log('detail data:', data);
    searchFormData.value = {};
    groupData.value = []; // 清空分组数据

    // 创建table
    if (data.tool_type === 'data_search'
      && Array.isArray(data.config.output_fields)) {
      columns.value = data.config.output_fields.map((item) => {
        const renderCell = createRenderCell(item, data);
        return {
          label: item.display_name,
          field: item.raw_name,
          minWidth: 200,
          showOverflowTooltip: true,
          render: renderCell,
        };
      });
    } else if (data.tool_type === 'api'
      && data.config.output_config
      && Array.isArray(data.config.output_config.groups)) {
      const outputConfig = data.config.output_config;
      // 为每个 group 处理 kv_fields 和 table_fields
      groupData.value = outputConfig.groups.map((group: any) => {
        const kvFields: GroupTableConfig['kv_fields'] = [];
        const tableFields: GroupTableConfig['table_fields'] = [];

        // 遍历每个 output_field，根据 field_config.field_type 分类
        (group.output_fields || []).forEach((field: any) => {
          const fieldConfig = field.field_config || {};
          const fieldType = fieldConfig.field_type;

          if (fieldType === 'kv') {
            // KV 模式：放入 kv_fields
            kvFields.push({
              raw_name: field.raw_name,
              enum_mappings: field.enum_mappings,
              drill_config: field.drill_config,
              display_name: field.display_name || field.raw_name,
              description: field.description || '',
              path: field.json_path || '',
              resolvePathValue: '', // 根据path解析的值
            });
          } else if (fieldType === 'table' && Array.isArray(fieldConfig.output_fields)) {
            // Table 模式：用 field_config.output_fields 生成 columns
            const tableColumns = fieldConfig.output_fields.map((item: OutputFields) => ({
              label: item.display_name || item.raw_name,
              field: item.raw_name,
              minWidth: 200,
              showOverflowTooltip: true,
              render: createRenderCell(item, data),
            }));

            tableFields.push({
              raw_name: field.raw_name,
              display_name: field.display_name || field.raw_name,
              description: field.description || '',
              path: field.json_path || '',
              columns: tableColumns,
              tableData: [],
              pagination: {
                count: 0,
                limit: 100,
                current: 1,
                limitList: [100, 200, 500, 1000],
              },
            });
          }
        });

        return {
          kv_fields: kvFields,
          table_fields: tableFields,
        };
      });
    }

    // 构造formData
    data.config.input_variable.forEach((item) => {
      searchFormData.value[item.raw_name] = '';
    });

    // 构造form-item
    const searchListAr = data.config.input_variable.map(item => ({
      ...item,
      // eslint-disable-next-line no-nested-ternary
      value: item.default_value
        ? item.default_value
        : (item.field_category === 'person_select' || item.field_category === 'time_range_select')
          ? [] :  null,
      required: item.required,
      disabled: props.source === 'risk' && toolDetails.value?.tool_type === 'data_search',
    }));

    // 非下钻
    if (!isDrillDownOpen.value) {
      searchList.value = searchListAr;
    } else {
      // 下钻填充值
      if (!drillDownItemConfig.value
        || drillDownItemConfig.value.length === 0) {
        return;
      }

      // 创建配置项的映射表
      const configMap = new Map();
      drillDownItemConfig.value.forEach((configItem) => {
        configMap.set(configItem.source_field, configItem);
      });

      // 一次性完成映射
      searchList.value = searchListAr.map((searchItem: any) => {
        const configItem = configMap.get(searchItem.raw_name);
        if (!configItem) return searchItem;

        // 动态值处理逻辑
        let dynamicValue = '';
        if (configItem.target_value_type !== 'fixed_value') {
          if (configItem.target_field_type === 'basic' || !configItem.target_field_type) {
            // 从根对象取值
            dynamicValue = drillDownItemRowData.value?.[configItem.target_value] ?? searchItem.value;
          } else {
            // 从event_data对象取值
            dynamicValue = drillDownItemRowData.value?.event_data?.[configItem.target_value] ?? searchItem.value;
          }
        }

        return {
          ...searchItem,
          value: configItem.target_value_type === 'fixed_value'
            ? configItem.target_value
            : dynamicValue,
        };
      });
    }

    nextTick(() => {
      if (formItemRef.value) {
        // form-item赋值
        formItemRef.value.forEach((item: any, index: number) => {
          item?.setData(searchList.value[index].value);
        });
        nextTick(() => {
          formRef.value.clearValidate();
        });
        // 判断每个字段是否有值
        const validateField = (field: any) => {
          if (!field.required) {
            return true;
          }
          if (field.field_category === 'time_range_select') {
            return Array.isArray(field.value) && field.value.length > 0;
          }
          if (field.field_category === 'person_select') {
            if (Array.isArray(field.value)) {
              return field.value.length > 0;
            }
            return field.value !== '';
          }
          return field.value !== null && field.value !== '';
        };

        const isValid = props.source
          ? searchList.value.map(e => (e.required ? validateField(e) : true)).every(e => e)
          : searchList.value.every(validateField);

        if (isValid) {
          submit();
        }
      } else if (data.tool_type === 'api') {
        // api 可以没有input_variable，直接提交
        submit();
      }
    });
  };

  // 图表
  const loadScript = (src: string) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve(script);
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
    document.head.appendChild(script);
  });

  const handleError = (_type: 'dashboard' | 'chart' | 'action' | 'others', err: Error) => {
    if (err.data.code === '9900403') {
      const iamResult = new IamApplyDataModel(err.data.data || {});
      // 页面展示没权限提示
      emitBus('permission-page', iamResult);
    } else {
      messageError(err.message);
    }
  };

  const initBK = async  (id: string) => {
    const filters: Record<string, any> = {};
    const drillDownFilters: Record<string, any> = {};
    const constants: Record<string, any> = {};
    // 初始化将默认值添加到常量中
    toolDetails.value?.config.input_variable.forEach((item: any) => {
      if (item.default_value && (Array.isArray(item.default_value) ? item.default_value.length > 0 : true)) {
        if (item.field_category === 'variable') {
          constants[item.raw_name] = item.default_value || '';
        } else {
          filters[item.raw_name] = item.default_value;
        }
      } else {
        if (item.field_category === 'variable') {
          constants[item.raw_name] = '';
        }
      }
    });
    // 将风险工具参数添加到常量中
    if (riskToolParams.value && Object.keys(riskToolParams.value).length > 0) {
      Object.keys(riskToolParams.value).forEach((key) => {
        if (riskToolParams.value && key in riskToolParams.value) {
          constants[key] = riskToolParams.value[key];
        } else {
          constants[key] = '';
        }
      });
    }
    // 下钻 常量使用下钻的值
    if (isDrillDownOpen.value) {
      drillDownItemConfig.value.forEach((item) => {
        // 根据源字段名称查找对应的字段分类
        const fieldCategory = toolDetails.value?.config.input_variable
          .find((i: any) => i.raw_name === item.source_field)?.field_category;

        if (item.target_value_type === 'field') { // 目标值为字段引用类型
          if (item.target_field_type === 'basic' || !item.target_field_type) {
            // 从根对象中获取字段值
            if (fieldCategory === 'variable') {
              // 变量类型字段：存储到 constants 中，用于工具执行时的参数传递
              constants[item.source_field] = drillDownItemRowData.value?.[item.target_value] ?? '';
            } else {
              // 过滤器类型字段：存储到 drillDownFilters 中，用于数据过滤
              drillDownFilters[item.source_field] = drillDownItemRowData.value?.[item.target_value] ?? '';
            }
          } else {
            // 从 event_data 嵌套对象中获取字段值
            if (fieldCategory === 'variable') {
              // 变量类型字段：存储到 constants 中
              constants[item.source_field] = drillDownItemRowData.value?.event_data?.[item.target_value] ?? '';
            } else {
              // 过滤器类型字段：存储到 drillDownFilters 中
              drillDownFilters[item.source_field] = drillDownItemRowData.value?.event_data?.[item.target_value] ?? '';
            }
          }
        } else { // 目标值为固定值类型
          if (fieldCategory === 'variable') {
            // 变量类型字段：直接使用固定值，存储到 constants 中
            constants[item.source_field] = item.target_value || '';
          } else {
            // 过滤器类型字段：直接使用固定值，存储到 drillDownFilters 中
            drillDownFilters[item.source_field] = item.target_value;
          }
        }
      });
    }

    try {
      await loadScript('https://staticfile.qq.com/bkvision/pbb9b207ba200407982a9bd3d3f2895d4/latest/main.js');
      window.BkVisionSDK.init(
        `#panel-${uid.value}`,
        id,
        {
          apiPrefix: `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/bkvision/`,
          chartToolMenu: [
            { type: 'tool', id: 'fullscreen', build_in: true },
            { type: 'tool', id: 'refresh', build_in: true },
            { type: 'menu', id: 'excel', build_in: true },
          ],
          filters: isDrillDownOpen.value ? drillDownFilters : filters,
          constants,
          handleError,
        },
      );
    } catch (error) {
      console.error(error);
    }
  };

  // 下钻点击
  const handleFieldDownClick = (
    drillDownItem: DrillDownItem,
    drillDownItemRowData: Record<string, any>,
    activeUid?: string,
  ) => {
    emit('openFieldDown', drillDownItem, drillDownItemRowData, activeUid);
  };

  // 打开弹窗
  const handleOpenDialog = async (
    itemUid: string,
    isDrillDownItem?: DrillDownItem,
    isDrillDownItemRowData?: Record<string, any>,
    isActiveUid?: string,
    isRiskToolParams?: Record<string, any>,
    preview?: boolean,
  ) => {
    // 是否预览 （暂时用不上）
    isPreview.value = preview;
    isShow.value = true;
    dialogUid.value = itemUid;
    riskToolParams.value = isRiskToolParams;

    // 多工具下钻
    if (itemUid.includes('&')) {
      const uids = itemUid.split('&');

      // 默认激活第一个
      activeUid.value = isActiveUid || uids[0];

      // 创建tabs列表
      const tabs = uids.map(uid => ({
        uid,
        name: getToolNameAndType(uid).name,
      }));

      // 如果tabs列表长度大于1，则显示tabs
      if (tabs.length > 1) {
        isShowTags.value = true;
        nextTick(() => {
          dialogHeaderRef.value.initTabsValue(tabs, activeUid.value);
        });
      }
    } else {
      activeUid.value = itemUid;
    }

    // dialog层级
    const isNewIndex = sessionStorage.getItem('dialogIndex');
    if (isNewIndex) {
      dialogIndex.value = Number(isNewIndex) + 1;
    }
    nextTick(() => {
      sessionStorage.setItem('dialogIndex', String(dialogIndex.value));
    });

    // 下钻
    if (isDrillDownItem && isDrillDownItemRowData) {
      // 是否下钻
      isDrillDownOpen.value = true;

      // 下选节点
      drillDownItem.value = isDrillDownItem;

      // 下选节点drill_config的config
      drillDownItemConfig.value = isDrillDownItem?.drill_config
        .find(item => item.tool.uid === activeUid.value)?.config || [];

      // 下钻节点所在行数据
      drillDownItemRowData.value = isDrillDownItemRowData;
    }

    // 获取工具详情
    fetchToolsDetail({ uid: activeUid.value });
  };

  // 关闭弹窗
  const handleCloseDialog = () => {
    emit('close', dialogUid.value);
    handleReset();
    isShow.value = false;
    dialogWidth.value = '50%';
    isFullScreen.value = false;
  };

  // 放大
  const handleFullscreen = () => {
    isFullScreen.value = !isFullScreen.value;
  };

  watch(() => isFullScreen.value, (val) => {
    nextTick(() => {
      if (tableData.value.length > 0) {
        // 判断可视高度大于900px
        // eslint-disable-next-line no-nested-ternary
        dialogTableHeight.value = val ? (window.innerHeight >= 900 ? `${window.innerHeight * 0.57}px` : '40%') : '300px';
      }
      // eslint-disable-next-line no-nested-ternary
      dialogHeight.value = isFullScreen.value ? (window.innerHeight >= 900 ? `${window.innerHeight * 0.65}px` : `${window.innerHeight * 0.60}px`) : `${window.innerHeight * 0.50}px`;
    });
  });

  // 添加边框拖动逻辑
  const startResize = (e: MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = parseInt(dialogWidth.value, 10);
    const minWidth = window.innerWidth * 0.5; // 最小宽度为屏幕宽度的50%

    const onMouseMove = (moveEvent: MouseEvent) => {
      const dx = moveEvent.clientX - startX;
      const newWidth = Math.max(minWidth, startWidth + dx); // 确保宽度不小于minWidth
      dialogWidth.value = `${newWidth}px`;
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  // 添加左边框拖动逻辑
  const startResizeLeft = (e: MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = parseInt(dialogWidth.value, 10);
    const minWidth = window.innerWidth * 0.5; // 最小宽度为屏幕宽度的50%

    const onMouseMove = (moveEvent: MouseEvent) => {
      const dx = startX - moveEvent.clientX; // 向左拖动时dx为正
      const newWidth = Math.max(minWidth, startWidth + dx); // 确保宽度不小于minWidth
      dialogWidth.value = `${newWidth}px`;
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  // 添加底部边框拖动逻辑
  /*  const startResizeBottom = (e: MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = parseInt(dialogHeight.value, 10);
    const startTableHeight = parseInt(dialogTableHeight.value, 10);
    const minHeight = window.innerHeight * 0.5; // 对话框最小高度为屏幕高度的50%
    const minTableHeight = 300; // 表格最小高度为300px

    const onMouseMove = (moveEvent: MouseEvent) => {
      const dy = moveEvent.clientY - startY;
      const newHeight = Math.max(minHeight, startHeight + dy); // 确保对话框高度不小于minHeight
      dialogHeight.value = `${newHeight}px`;
      // 同步更新表格高度，确保不小于minTableHeight
      const newTableHeight = Math.max(minTableHeight, startTableHeight + dy);
      dialogTableHeight.value = `${newTableHeight - 20}px`;
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }; */

  // 点击头部标签
  const handleClickTag = (TagItem: any) => {
    activeUid.value = TagItem.uid;
    drillDownItemConfig.value = drillDownItem.value?.drill_config
      .find(item => item.tool.uid === activeUid.value)?.config || [];

    // 清空表格数据
    tableData.value = [];
    pagination.value.count = 0;

    fetchToolsDetail({ uid: activeUid.value });
  };

  defineExpose<Exposes>({
    closeDialog() {
      handleCloseDialog();
    },
    openDialog(itemUid, drillDownItem, drillDownItemRowData, activeUid, isRiskToolParams, preview) {
      handleOpenDialog(itemUid, drillDownItem, drillDownItemRowData, activeUid, isRiskToolParams, preview);
    },
    initTabsValue(tabs: Array<tabsItem>, id: string) {
      nextTick(() => {
        dialogHeaderRef.value.initTabsValue(tabs, id);
      });
    },
  });

</script>

<style scoped lang="postcss">
/* 添加边框拖动样式 */
.resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  z-index: 20001;
  width: 10px;
  height: 100%;
  cursor: ew-resize;
  opacity: 50%;
}

.resize-handle-left {
  position: absolute;
  bottom: 0;
  left: 0;
  z-index: 20001;
  width: 10px;
  height: 100%;
  cursor: ew-resize;
  opacity: 50%;
}

.resize-handle-top {
  position: absolute;
  bottom: 0;
  z-index: 20001;
  width: 100%;
  height: 10px;
  cursor: ns-resize;
  opacity: 50%;
}

.dialog-tool {
  padding-left: 24px;

  /* width: 100%; */
  background: #fafbfd;
}

.header {
  display: flex;
  padding: 0 24px;

  .header-left {
    position: absolute;
    top: 6px;
    right: 40px;

    .full-screen-img {
      width: 12.2px;
      height: 12.2px;
      cursor: pointer;
    }
  }

  .top-left-icon {
    width: 48px;
    height: 48px;
    border-radius: 4px;
  }

  .top-right {
    display: flex;

    .top-right-box {
      margin-left: 5px;

      .top-right-title {
        display: flex;
        width: 100%;
        overflow: hidden;
        font-size: 16px;
        font-weight: 700;
        line-height: 24px;
        letter-spacing: 0;
        color: #313238;
        text-overflow: ellipsis;
        white-space: nowrap;
        align-items: center;

        .top-right-name {
          display: inline-block;
          max-width: 300px;
          margin-right: 5px;
          overflow: hidden;
          text-overflow: ellipsis;
          align-items: center;
        }

        .desc-tag {
          margin-right: 5px;
          font-size: 12px;
          font-weight: 500;
          line-height: 22px;
          color: #4d4f56;
          text-align: left
        }

        .desc-tag-info {
          color: #1768ef;
          cursor: pointer;
        }
      }

      .top-right-desc {
        font-size: 14px;
        line-height: 22px;
        letter-spacing: 0;
        color: #313238;
      }
    }

  }
}

.panel {
  min-height: 50vh;
}

.top-line {
  width: 100%;
  height: 1px;
  margin-top: 10px;
  background: #d8d8d8;
}

.top-search {
  margin-top: 32px;

  .top-search-title {
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    letter-spacing: 0;
    color: #313238;
  }

  .top-search-result {
    position: relative;
    height: auto;
    padding: 10px;
    margin-top: 10px;

    .top-search-table-title {
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      letter-spacing: 0;
      color: #313238;
    }
  }

  .example {
    margin-top: 10px;

    .formref-item {
      display: flex;
      flex-wrap: wrap;

      .formref-item-item {
        width: 300px;
        margin-right: 15px;
      }
    }
  }

  .list-data {
    margin-top: 10px;
  }
}

.default-permission {
  position: relative;
  height: 70vh;

  .no-permission {
    position: absolute;
    top: 30%;
    left: 50%;
    text-align: center;
    transform: translate(-50%, -30%);

    .no-permission-img {
      width: 200px;
      height: 200px;
      margin: 0 auto;
    }

    .no-permission-desc {
      margin-top: 16px;

      .no-permission-title {
        margin-bottom: 8px;
        font-size: 16px;
        font-weight: bold;
        color: #4d4f56;
      }

      .no-permission-text {
        margin-bottom: 12px;
        font-size: 14px;
        color: #63656e;
      }

      .no-permission-btn {
        font-size: 14px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }
}

:deep(.bk-table .bk-table-head .col-resize-drag) {
  background-color: #fafbfd;
}
</style>
<style lang="postcss">
.tools-use-dialog {
  .bk-modal-body {
    border-radius: 16px 16px 8px 8px;

    .bk-dialog-tool {
      height: 0;
    }

    .bk-dialog-header {
      padding: 0;
    }
  }

  .bk-card {
    margin-bottom: 16px;

    .bk-card-head {
      height: 32px;
      line-height: 32px;
      background-color: #f0f1f5;
    }

    .bk-card-body {
      padding: 0 16px;
      background-color: #fafbfd;
    }

    .card-content {
      padding: 16px 0;

      .kv-field-item {
        .info-label {
          flex: 1;
        }
      }
    }
  }

}
</style>
