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
                  class="desc-tag">
                  + {{ itemInfo.tags.length - 3
                  }}
                </bk-tag>
                <bk-tag
                  class="desc-tag desc-tag-info"
                  theme="info">
                  运用在 0 个策略中
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
          :style="isFullScreen ? `height:${dialogHeight}` : ''">
          <div class="top-line" />
          <div v-if="itemInfo?.permission?.use_tool">
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
                    <form-item
                      ref="formItemRef"
                      :data-config="item"
                      @change="(val) => handleFormItemChange(val, item)" />
                  </bk-form-item>
                </div>
              </bk-form>
              <div>
                <bk-button
                  class="mr8"
                  theme="primary"
                  @click="submit">
                  查询
                </bk-button>
                <bk-button
                  class="mr8"
                  @click="handleReset">
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
                    :border="['outer', 'col', 'row']"
                    :columns="columns"
                    :data="tableData"
                    max-height="50vh"
                    :pagination="pagination"
                    width="100%"
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
                <p class="no-permission-btn">
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
            id="panel"
            class="panel" />
        </div>
      </template>
      <template #footer />
    </bk-dialog>
  </div>
</template>
<script setup lang='tsx'>
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import IamApplyDataModel from '@model/iam/apply-data';
  import ToolDetailModel from '@model/tool/tool-detail';
  import ToolInfo from '@model/tool/tool-info';

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
  }
  interface Props {
    tagsEnums: Array<TagItem>,
  }

  interface TableDataItem {
    [key: string]: any;
  }
  interface Exposes {
    closeDialog: () => void,
    openDialog: (item: ToolInfo, isDrillDown: boolean, drillDownItem: any, preview?: boolean) => void,
  }
  interface Emits {
    (e: 'openFieldDown', val: string, isDrillDown: boolean): void;
    (e: 'close'): void;
  }
  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const   emitBus  = useEventBus().emit;
  const { messageError } = useMessage();
  const { t } = useI18n();

  const dialogIndex = ref(2000);
  const dialogWidth = ref('1000px');
  const dialogHeight = ref('80vh');

  const isFullScreen = ref(false);
  const isLoading = ref(false);
  const isShow = ref(false);
  const isPreview = ref<boolean | undefined>(false);

  const dialogRef = ref();
  const formItemRef = ref();

  const itemInfo = ref<ToolInfo>();
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
  const rules = {};
  const formRef = ref();
  const searchForm = ref();

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

  // 获取表格数据的方法（需要根据实际业务实现）
  const fetchTableData = () => {
    isLoading.value = true;
    fetchToolsExecute({
      uid: uid.value,
      page: pagination.value.current,
      page_size: pagination.value.limit,
      params: itemInfo.value?.tool_type === 'data_search' ? {
        tool_variables: searchList.value.map(item => ({
          raw_name: item.raw_name,
          value: item.value || '',
        })),
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

  const itemIcon = (item: ToolInfo) => {
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
    formRef.value.validate().then(() => {
      fetchTableData();
    });
  };

  // 清空表单验证
  const handleReset = () => {
    formRef.value.clearValidate();
    Object.keys(searchForm.value).forEach((key) => {
      searchForm.value[key] = '';
    });
    searchList.value = searchList.value.map(item => ({
      ...item,
      value: null,
    }));
    pagination.value.current = 1;
    pagination.value.count = 0;
    pagination.value.limit = 100;
    tableData.value = [];
    if (formItemRef.value) {
      formItemRef.value.forEach((item: any) => {
        item?.resetValue();
      });
    }
  };

  const handleFormItemChange = (val: any, item: SearchItem) => {
    // 完全避免修改函数参数item
    const index = searchList.value.findIndex(i => i.raw_name === item.raw_name);
    if (index !== -1) {
      searchList.value = [
        ...searchList.value.slice(0, index),
        {
          ...searchList.value[index],
          value: val,
        },
        ...searchList.value.slice(index + 1),
      ];
    }
    searchForm.value[item.raw_name] = val;
  };

  // 创建弹窗内容
  const createDialogContent = (data: ToolDetailModel) => {
    searchForm.value = {};
    searchList.value = data.config.input_variable.map(item => ({
      ...item,
      value: null,
      required: item.required, // 将字符串类型的required转换为布尔值
    }));
    data.config.input_variable.forEach((item) => {
      searchForm.value[item.raw_name] = '';
    });
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
            handleFieldDownClick(item);
          }}
          >{data[item.raw_name]} </bk-button>,
      };
    });
  };

  // 获取工具详情
  const {
    run: fetchToolsDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      uid.value = data.uid;
      // bkVision直接请求
      if (data.tool_type !== 'data_search') {
        fetchTableData();
      } else {
        // 创建弹框form、table
        createDialogContent(data);
      }
    },
  });

  // 下钻点击
  const handleFieldDownClick = (data: any) => {
    emit('openFieldDown', data, true);
  };

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

  // 打开弹窗
  const handleOpenDialog = async (item: ToolInfo, isDrillDown: boolean, drillDownItem: any, preview?: boolean) => {
    isShow.value = true;
    itemInfo.value = item;
    isPreview.value = preview;

    const isNewIndex = sessionStorage.getItem('dialogIndex');
    if (isNewIndex) {
      dialogIndex.value = Number(isNewIndex) + 1;
    }
    nextTick(() => {
      sessionStorage.setItem('dialogIndex', String(dialogIndex.value));
    });
    // 等待两次nextTick确保DOM完全更新
    await nextTick();
    await nextTick();
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

    if (isPreview.value) {
      const detail = new ToolDetailModel();
      createDialogContent({
        ...detail,
        ...item,
      } as ToolDetailModel);
      return;
    }

    fetchToolsDetail({ uid: item.uid })
      .then(() => {
        // 下钻打开传递参数
        if (isDrillDown) {
          drillDownItem.drill_config.config.forEach((el:any) => {
            searchList.value = searchList.value.map((searchItem: any) => {
              if (searchItem.raw_name === el.source_field) {
                return {
                  ...searchItem,
                  value: el.target_value,
                };
              }
              return searchItem;
            });
          });
        }
      });
  };

  const handleCloseDialog = () => {
    emit('close');
    isShow.value = false;
    handleReset();
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
    try {
      await loadScript('https://staticfile.qq.com/bkvision/pbb9b207ba200407982a9bd3d3f2895d4/latest/main.js');
      window.BkVisionSDK.init(
        '#panel',
        id,
        {
          apiPrefix: `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/bkvision/`,
          chartToolMenu: [
            { type: 'tool', id: 'fullscreen', build_in: true },
            { type: 'tool', id: 'refresh', build_in: true },
            { type: 'menu', id: 'excel', build_in: true },
          ],
          handleError,
        },
      );
    } catch (error) {
      console.error(error);
    }
  };

  // 放大
  const handleFullscreen = () => {
    isFullScreen.value = !isFullScreen.value;
    dialogWidth.value = isFullScreen.value ? '90%' : '1000px';
  };

  defineExpose<Exposes>({
    closeDialog() {
      handleCloseDialog();
    },
    openDialog(item, isDrillDown, drillDownItem, preview) {
      handleOpenDialog(item, isDrillDown, drillDownItem, preview);
    },
  });
</script>

<style scoped lang="postcss">
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
      width: 90%;
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
</style>
