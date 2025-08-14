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
  <div>
    <bk-dialog
      ref="dialogRef"
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
        <div class="header">
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
              :type="itemInfo ? itemIcon(itemInfo) : ''" />
            <div class="top-right-box">
              <div class="top-right-title">
                <span
                  v-bk-tooltips="{
                    disabled: !isTextOverflow(itemInfo?.name || '', 0, '300px', { isSingleLine: true }),
                    content: t(itemInfo?.name || ''),
                    placement: 'top',
                  }"
                  class="top-right-name">
                  {{ itemInfo?.name }}
                </span>
                <bk-tag
                  v-for="(tag, tagIndex) in itemInfo?.tags.slice(0, 3)"
                  :key="tagIndex"
                  class="desc-tag">
                  {{ returnTagsName(tag) }}
                </bk-tag>
                <bk-tag
                  v-if="itemInfo?.tags && itemInfo.tags.length > 3"
                  v-bk-tooltips="{
                    content: tagContent(itemInfo.tags),
                    placement: 'top',
                  }"
                  class="desc-tag">
                  + {{ itemInfo.tags.length - 3
                  }}
                </bk-tag>
                <bk-tag
                  class="desc-tag desc-tag-info"
                  theme="info"
                  @click="handlesStrategiesClick(itemInfo)">
                  运用在 {{ itemInfo?.strategies.length }} 个策略中
                </bk-tag>
              </div>
              <div class="top-right-desc">
                {{ itemInfo?.description }}
              </div>
            </div>
          </div>
        </div>
      </template>
      <template #default>
        <div
          v-if="itemInfo?.tool_type !== 'bk_vision'"
          class="default"
          :style="`height:${dialogHeight}`">
          <div class="top-line" />
          <div v-if="permission">
            <div class="top-search">
              <div class="top-search-title">
                {{ t('查询输入') }}
              </div>
              <bk-form
                ref="formRef"
                class="example"
                form-type="vertical"
                :model="searchForm"
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
              <div>
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
                  <bk-table
                    :border="['row','outer','col']"
                    :columns="columns"
                    :data="tableData"
                    header-align="center"
                    :height="dialogTableHeight"
                    min-height="200px"
                    :pagination="pagination"
                    remote-pagination
                    show-overflow-tooltip
                    @page-limit-change="handlePageLimitChange"
                    @page-value-change="handlePageChange" />
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
        </div>

        <div
          v-else
          class="default">
          <div class="top-line" />
          <div
            :id="`panel-${uid}`"
            ref="panelRef"
            class="panel" />
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
        <div
          v-if="!isFullScreen"
          class="resize-handle-top"
          @mousedown="startResizeBottom" />
      </template>
    </bk-dialog>
  </div>
</template>
<script setup lang='tsx'>
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import ToolManageService from '@service/tool-manage';

  import IamApplyDataModel from '@model/iam/apply-data';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useMessage from '@hooks/use-message';

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
  }
  interface Props {
    tagsEnums: Array<TagItem>,
  }
  interface DrillDownItem {
    raw_name: string;
    display_name: string;
    description: string;
    drill_config: {
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
        target_field_type?: string;
      }>
    };
  }
  interface TableDataItem {
    [key: string]: any;
  }
  interface Exposes {
    closeDialog: () => void,
    openDialog: (
      itemUid: string,  // 工具信息
      drillDownItem?: DrillDownItem, // 下钻信息
      drillDownItemRowData?: Record<string, string>, // 下钻table所在行信息
      preview?: boolean // 是否预览
    ) => void,
  }
  interface Emits {
    (e: 'openFieldDown', drillDownItem: DrillDownItem, drillDownItemRowData: Record<string, any>): void;
    (e: 'close', val?: ToolDetailModel): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const   emitBus  = useEventBus().emit;
  const { messageError } = useMessage();
  const { t } = useI18n();

  const dialogIndex = ref(2000);
  const dialogWidth = ref('50%');
  const dialogHeight = ref('50vh');
  const dialogTableHeight = ref('300px');
  const isFullScreen = ref(false);
  const isLoading = ref(false);
  const isShow = ref(false);
  const isPreview = ref<boolean | undefined>(false);
  const isDrillDownOpen = ref(false);
  const permission = ref(true);
  const dialogRef = ref();
  const formItemRef = ref();

  const itemInfo = ref<ToolDetailModel>();
  const searchList = ref<SearchItem[]>([]);
  const tableData = ref<TableDataItem[]>([]);
  const columns = ref<Column[]>([]);
  const pagination = ref({
    count: 0,
    limit: 100,
    current: 1,
    limitList: [100, 200, 500, 1000],
  });
  const uid = ref('');
  const panelId = ref('');
  const panelRef = ref();
  const rules = ref({});
  const formRef = ref();
  const searchForm = ref();
  const router = useRouter();

  const drillDownItemConfig = ref<DrillDownItem['drill_config']['config']>([]);
  const drillDownItemRowData = ref<Record<string, any>>({});

  // 工具执行
  const {
    run: fetchToolsExecute,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      if (data === undefined) {
        tableData.value = [];
      }
      if (itemInfo.value?.tool_type === 'data_search') {
        tableData.value = JSON.parse(JSON.stringify(data.data.results));
        pagination.value.count = data.data.total;
      } else {
        panelId.value = data.data.panel_id;
        initBK(data.data.panel_id);
      }
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
  const toolDetails = ref<ToolDetailModel>();
  // 获取工具详情
  const {
    run: fetchToolsDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      uid.value = data.uid;
      permission.value = data.permission.use_tool;
      toolDetails.value = data;
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

  // 获取表格数据的方法
  const fetchTableData = () => {
    isLoading.value = true;
    fetchToolsExecute({
      uid: uid.value,
      params: itemInfo.value?.tool_type === 'data_search' ? {
        tool_variables: searchList.value.map(item => ({
          raw_name: item.raw_name,
          value: item.value,
        })),
        page: pagination.value.current,
        page_size: pagination.value.limit,
      } : {},
    })
      .finally(() => {
        isLoading.value = false;
      });
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

  const submit = () => {
    searchList.value.forEach((item) => {
      searchForm.value[item.raw_name] = item.value;
    });
    formRef.value.validate().then(() => {
      formItemRef.value.forEach((item: any) => {
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
      target.value = val;
    }

    searchForm.value[item.raw_name] = val;
  };

  // 创建弹窗内容
  const createDialogContent = (data: ToolDetailModel) => {
    searchForm.value = {};
    // 创建table
    columns.value = data.config.output_fields.map((item) => {
      if (item.drill_config === null || item.drill_config?.tool.uid === '') {
        return {
          label: item.display_name,
          field: item.raw_name,
          minWidth: 200,
          showOverflowTooltip: true,
        };
      }
      return {
        label: item.display_name,
        field: item.raw_name,
        minWidth: 200,
        showOverflowTooltip: true,
        render: ({ data }: {data: Record<any, string>}) => <bk-button  theme="primary" text
           onClick={(e:any) => {
            e.stopPropagation(); // 阻止事件冒泡
            handleFieldDownClick(item, data);
          }}
          >{data[item.raw_name]} </bk-button>,
      };
    });

    // 构造formData
    data.config.input_variable.forEach((item) => {
      searchForm.value[item.raw_name] = '';
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
        const isValid = searchList.value.every((e) => {
          if (e.field_category === 'person_select' || e.field_category === 'time_range_select') {
            return Array.isArray(e.value) && e.value.length > 0;
          }
          return e.value !== null && e.value !== '';
        });
        if (isValid) {
          submit();
        }
      }
    });
  };

  // 权限
  const urlIamApply = ref('');
  const handleIamApply = () => {
    window.open(urlIamApply.value, '_blank');
  };

  const {
    run: getApplyData,
  } = useRequest(IamManageService.getApplyData, {
    defaultValue: new IamApplyDataModel(),
    onSuccess(result) {
      urlIamApply.value = result.apply_url;
    },
  });

  // 放大
  const handleFullscreen = () => {
    isFullScreen.value = !isFullScreen.value;
  };

  const isTextOverflow = (text: string, maxHeight = 0, width: string, options: {
    isSingleLine?: boolean;
    fontSize?: string;
    fontWeight?: string;
    lineHeight?: string;
  } = {}) => {
    if (!text) return false;

    const {
      isSingleLine = maxHeight === 0, // 默认单行检测
      fontSize = isSingleLine ? '16px' : '14px',
      fontWeight = isSingleLine ? '700' : 'normal',
      lineHeight = '22px',
    } = options;

    const temp = document.createElement('div');
    temp.style.position = 'absolute';
    temp.style.visibility = 'hidden';
    temp.style.width = width;
    temp.style.fontSize = fontSize;
    temp.style.fontWeight = fontWeight;
    temp.style.fontFamily = 'inherit';
    temp.style.lineHeight = lineHeight;
    temp.style.boxSizing = 'border-box';
    temp.textContent = text;

    if (isSingleLine) {
      temp.style.whiteSpace = 'nowrap';
      temp.style.overflow = 'visible';
    } else {
      temp.style.display = '-webkit-box';
      temp.style.webkitLineClamp = '2';
      temp.style.overflow = 'hidden';
    }

    document.body.appendChild(temp);

    const isOverflow = maxHeight > 0
      ? temp.scrollHeight > maxHeight
      : temp.scrollWidth > temp.offsetWidth;

    document.body.removeChild(temp);
    return isOverflow;
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
    toolDetails.value?.config.input_variable.forEach((item: any) => {
      filters[item.raw_name] = item.default_value;
    });
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
          filters: isDrillDownOpen.value ? drillDownBkVisionVConfig.value : filters,
          handleError,
        },
      );
    } catch (error) {
      console.error(error);
    }
  };

  // 下钻点击
  const handleFieldDownClick = (drillDownItem: DrillDownItem, drillDownItemRowData: Record<string, any>) => {
    emit('openFieldDown', drillDownItem, drillDownItemRowData);
  };
  // bkVision下钻
  const drillDownBkVisionVConfig = ref<Record<string, any>>({});
  // 打开弹窗
  const handleOpenDialog = async (
    itemUid: string,
    drillDownItem?: DrillDownItem,
    isDrillDownItemRowData?: Record<string, any>,
    preview?: boolean,
  ) => {
    // 下钻
    if (drillDownItem && isDrillDownItemRowData) {
      // 是否下钻
      isDrillDownOpen.value = true;
      // 下选父节点drill_config的config
      drillDownItemConfig.value = drillDownItem?.drill_config?.config;
      // 下钻父节点所在行数据
      drillDownItemRowData.value = isDrillDownItemRowData;

      drillDownItem?.drill_config.config.forEach((e: any) => {
        if (e.target_value_type === 'field') { // 直接应用值
          drillDownBkVisionVConfig.value[e.source_field]  = isDrillDownItemRowData?.[e.target_value];
        } else { // 使用默认值
          drillDownBkVisionVConfig.value[e.source_field] = e.target_value;
        }
      });
    }
    // 是否预览 （暂时用不上）
    isPreview.value = preview;

    isShow.value = true;
    // itemInfo.value = item;

    const isNewIndex = sessionStorage.getItem('dialogIndex');
    if (isNewIndex) {
      dialogIndex.value = Number(isNewIndex) + 1;
    }
    nextTick(() => {
      sessionStorage.setItem('dialogIndex', String(dialogIndex.value));
    });


    // 获取工具详情
    fetchToolsDetail({ uid: itemUid }).then((res: ToolDetailModel) => {
      isShow.value = true;
      itemInfo.value = res;

      // 权限
      if (!res?.permission.use_tool) {
        getApplyData({
          action_ids: 'use_tool',
          resources: res.uid,
        });
      }
      // 预览 （暂时用不上）
      if (isPreview.value) {
        const detail = new ToolDetailModel();
        createDialogContent({
          ...detail,
          ...res,
        } as ToolDetailModel);
        return;
      }
      // bkVision直接请求
      if (res.tool_type !== 'data_search') {
        fetchTableData();
      } else {
        // 创建弹框form、table
        createDialogContent(res);
      }
      setTimeout(() => {
        const modals = document.getElementsByClassName('bk-modal-wrapper');

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
    });
  };

  const handleCloseDialog = () => {
    emit('close', itemInfo.value);
    handleReset();
    isShow.value = false;
    dialogWidth.value = '50%';
    isFullScreen.value = false;
  };
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
  const startResizeBottom = (e: MouseEvent) => {
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
  };
  defineExpose<Exposes>({
    closeDialog() {
      handleCloseDialog();
    },
    openDialog(itemUid, drillDownItem, drillDownItemRowData, preview) {
      handleOpenDialog(itemUid, drillDownItem, drillDownItemRowData, preview);
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

.header {
  display: flex;

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

.default {
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

      /* background-color: blueviolet; */
      height: auto;
      padding: 10px;
      margin-top: 10px;
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

}

:deep(.bk-table .bk-table-head .col-resize-drag) {
  background-color: #fafbfd;
}
</style>
