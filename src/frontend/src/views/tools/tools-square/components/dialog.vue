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
      :ext-cls="dialogCls"
      :is-show="isShow"
      render-directive="show"
      :show-mask="false"
      :style="{
        'z-index': dialogIndex,
        'position': 'absolute'
      }"
      width="40%"
      :z-index="dialogIndex"
      @click="handleClick"
      @closed="handleCloseDialog">
      <template #header>
        <div class="header">
          <div class="header-left">
            <!-- <img
              class="full-screen-img"
              src="@images/fullScreen.png"> -->
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
        <div class="default">
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
                <bk-table
                  :border="['outer', 'col', 'row']"
                  :columns="columns"
                  :data="tableData"
                  max-height="50vh"
                  min-height="300px"
                  :pagination="pagination"
                  width="100%"
                  @page-limit-change="handlePageLimitChange"
                  @page-value-change="handlePageChange" />
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
      </template>

      <template #footer />
    </bk-dialog>
  </div>
</template>
<script setup lang='tsx'>
  import { nextTick, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolsSquare from '@service/tools-square';

  import type ToolDetail from '@model/tool/tool-detail';
  import toolInfo from '@model/tools-square/tools-square';

  import useRequest from '@/hooks/use-request';
  import FormItem from '@/views/tools/tools-square/components/form-item.vue';

  interface Column {
    label: string;
    field: string;
    width?: number;
    minWidth?: number;
    sortable?: boolean;
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
    dialogCls: string,
    tagsEnums: Array<TagItem>,
  }

  interface TableDataItem {
    [key: string]: any;
  }
  interface Exposes {
    closeDialog: () => void,
    openDialog: (item: toolInfo) => void,
  }
  const props = defineProps<Props>();
  const dialogIndex = ref(2000);
  const { t } = useI18n();
  const isShow = ref(false);
  const uid = ref('');
  const rules = {};
  const formRef = ref();
  const itemInfo = ref<toolInfo>();
  const dialogRef = ref();
  const searchForm = ref();
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

  // 处理页码变化
  const handlePageChange = (newPage: number) => {
    console.log('处理页码变化');
    pagination.value.current = newPage;
    fetchTableData(); // 调用获取表格数据的方法
  };
  // 处理每页条数变化
  const handlePageLimitChange = (newLimit: number) => {
    console.log('处理每页条数变化');
    pagination.value.limit = newLimit;
    pagination.value.current = 1; // 重置到第一页
    fetchTableData(); // 调用获取表格数据的方法
  };

  // 获取表格数据的方法（需要根据实际业务实现）
  const fetchTableData = () => {
    // fetchToolsExecute({
    //   uid: "3aa8a524564711f083bb0a97de54c4dd",
    //   page: pagination.value.current,
    //   page_size: pagination.value.limit,
    //   params: {
    //     tool_variables: [
    //       {
    //       raw_name: "thedate",
    //       value: "20250707",
    //     }
    //     ],
    //   },
    // }).then((data) =>{
    //   if(data === undefined){
    //   columns.value = [{}  as Column];
    //   tableData.value = []
    //   }
    // })
    fetchToolsExecute({
      uid: uid.value,
      page: pagination.value.current,
      page_size: pagination.value.limit,
      params: {
        tool_variables: searchList.value.map(item => ({
          raw_name: item.raw_name,
          value: item.value,
        })),
      },
    }).then((data) => {
      if (data === undefined) {
        columns.value = [{}  as Column];
        tableData.value = [];
      }
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

  const itemIcon = (item: toolInfo) => {
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
  const handleReset = () => {
    // 调用每个FormItem组件的resetValue方法
    if (formItemRef.value) {
      formItemRef.value.forEach((item: any) => {
        item?.resetValue?.();
      });
    }
    // 清空表单验证
    formRef.value.clearValidate();
    // 重置searchForm中所有字段为空
    Object.keys(searchForm.value).forEach((key) => {
      searchForm.value[key] = '';
    });

    // 重置searchList中所有项的value为null
    searchList.value = searchList.value.map(item => ({
      ...item,
      value: null,
    }));
  };


  const handleFormItemChange = (val: any, item: SearchItem) => {
    // 避免直接修改函数参数，改为更新searchList中的对应项
    const index = searchList.value.findIndex(i => i.raw_name === item.raw_name);
    if (index !== -1) {
      searchList.value[index].value = val;
    }
    searchForm.value[item.raw_name] = val;
  };
  // 获取工具详情
  const {
    run: fetchToolsDetail,
  } = useRequest(ToolsSquare.fetchToolsDetail, {
    defaultValue: {} as ToolDetail,
    onSuccess: (data: ToolDetail) => {
      uid.value = data.uid;
      searchForm.value = {};
      searchList.value = data.config.input_variable.map(item => ({
        ...item,
        value: null,
        required: item.required === 'true', // 将字符串类型的required转换为布尔值
      }));
      data.config.input_variable.forEach((item) => {
        searchForm.value[item.raw_name] = '';
      });
      fetchTableData();
    },
  });

  // 工具执行
  const {
    run: fetchToolsExecute,
  } = useRequest(ToolsSquare.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      tableData.value = JSON.parse(JSON.stringify(data.data.results));
      columns.value = data.data.results.reduce((acc: Column[], item: any) => {
        Object.keys(item).forEach((key) => {
          // 检查是否已存在该列的配置
          if (!acc.some(col => col.field === key)) {
            acc.push({
              label: key,
              field: key,
              minWidth: 200,
            });
          }
        });
        return acc;
      }, []);
      pagination.value.count = data.data.total;
    },
  });

  const handleOpenDialog = async (item: toolInfo) => {
    isShow.value = true;
    itemInfo.value = item;
    fetchToolsDetail({ uid: item.uid });
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
  };

  const handleCloseDialog = () => {
    isShow.value = false;
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

  onMounted(() => {


  });

  defineExpose<Exposes>({
    closeDialog() {
      handleCloseDialog();
    },
    openDialog(item) {
      handleOpenDialog(item);
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
