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
    @click="handleClickDialog"
    @closed="handleCloseDialog">
    <template #header>
      <div
        v-if="isShowTags"
        class="dialog-tool">
        <dialog-header
          ref="dialogHeaderRef"
          :tabs="tabs"
          @click-item="handleChangeTool" />
      </div>
      <div
        class="header"
        :style="`margin-top: ${isShowTags ? '10px' : '24px'};`">
        <div class="header-left">
          <audit-icon
            class="full-screen-img"
            svg
            :type="isFullScreen ? 'un-full-screen-2' : 'full-screen'"
            @click="() => isFullScreen = !isFullScreen" />
        </div>
        <div class="top-right">
          <audit-icon
            class="top-left-icon"
            svg
            :type="toolDetails ? toolIconMap[toolDetails.tool_type] || '' : ''" />
          <div class="top-right-box">
            <div class="top-right-title">
              <tool-tips
                class="top-right-name"
                :data="toolDetails?.name || ''" />
              <bk-tag
                v-for="(tag, tagIndex) in toolDetails?.tags?.slice(0, 3)"
                :key="tagIndex"
                class="desc-tag">
                {{ tagsEnums.find(item => item.tag_id === tag)?.tag_name || tag }}
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
            <!-- 有权限时 -->
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
                      v-show="item?.is_show !== false"
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
                    <data-search-result
                      v-if="toolDetails?.tool_type === 'data_search'"
                      ref="dataSearchResultRef"
                      :get-tool-name-and-type="getToolNameAndType"
                      :max-height="dialogTableHeight"
                      remote-pagination
                      :risk-tool-params="riskToolParams"
                      :search-list="searchList"
                      :tool-details="toolDetails"
                      :uid="uid"
                      @handle-field-down-click="handleFieldDownClick" />

                    <!-- api工具 -->
                    <api-search-result
                      v-show="toolDetails?.tool_type === 'api'"
                      ref="apiSearchResultRef"
                      :get-tool-name-and-type="getToolNameAndType"
                      :max-height="dialogTableHeight"
                      :risk-tool-params="riskToolParams"
                      :search-list="searchList"
                      :tool-details="toolDetails"
                      :uid="uid"
                      @handle-field-down-click="handleFieldDownClick" />
                  </bk-loading>
                </div>
              </div>
            </div>
            <!-- 无权限时 -->
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
          <bk-vision-result
            v-if="toolDetails?.tool_type === 'bk_vision'"
            ref="bkVisionResultRef"
            :drill-down-item-config="drillDownItemConfig"
            :drill-down-item-row-data="drillDownItemRowData"
            :is-drill-down-open="isDrillDownOpen"
            :risk-tool-params="riskToolParams"
            :search-list="searchList"
            :tool-details="toolDetails"
            :uid="uid" />
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
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import ToolManageService from '@service/tool-manage';

  import IamApplyDataModel from '@model/iam/apply-data';
  // import type { OutputFields } from '@model/tool/tool-detail';
  import ToolDetailModel from '@model/tool/tool-detail';

  import ToolTips from '@components/show-tooltips-text/index.vue';

  import ApiSearchResult from './api-search-result.vue';
  import BkVisionResult from './bk-vision-result.vue';
  import DataSearchResult from './data-search-result.vue';
  import DialogHeader from './dialog-header.vue';

  import useRequest from '@/hooks/use-request';
  import FormItem from '@/views/tools/tools-square/components/form-item.vue';

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
    is_show?: boolean;
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
  interface tabsItem {
    uid: string;
    name: string;
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
  const { t } = useI18n();

  const toolIconMap: Record<string, string> = {
    data_search: 'sqlxiao',
    bk_vision: 'bkvisonxiao',
    api: 'apixiao',
  };

  const dialogHeaderRef = ref();
  const dialogIndex = ref(3000);
  const dialogWidth = ref('50%');
  const dialogHeight = ref('50vh');
  const dialogTableHeight = ref('300px');
  const isFullScreen = ref(false);
  const isShow = ref(false);
  const isPreview = ref<boolean | undefined>(false);
  const isDrillDownOpen = ref(false);
  const formItemRef = ref();

  const uid = ref('');
  const rules = ref({});
  const formRef = ref();
  const dataSearchResultRef = ref();
  const apiSearchResultRef = ref();
  const bkVisionResultRef = ref();

  const router = useRouter();
  const tabs = ref<Array<tabsItem>>([]);
  const drillDownItemConfig = ref<DrillDownItem['drill_config'][0]['config']>([]);
  const drillDownItemRowData = ref<Record<string, any>>({});
  const drillDownItem = ref<DrillDownItem>();

  const riskToolParams = ref<Record<string, any> | undefined>(undefined);
  const dialogUid = ref('');
  const isShowTags = ref(false);

  // 当前激活的工具
  const activeUid = ref('');

  const searchList = ref<SearchItem[]>([]);

  const searchFormData = computed(() => {
    const formData: Record<string, any> = {};
    searchList.value.forEach((item) => {
      formData[item.raw_name] = item.value;
    });
    return formData;
  });

  // const toolExecuteData = computed(() => {
  //   if (apiSearchResultRef.value) {
  //     return apiSearchResultRef.value.toolExecuteData;
  //   }
  //   return null;
  // });

  const isLoading = computed(() => {
    if (dataSearchResultRef.value) {
      return dataSearchResultRef.value.isLoading;
    }
    if (apiSearchResultRef.value) {
      return apiSearchResultRef.value.isLoading;
    }
    return false;
  });


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

      if (data.tool_type !== 'bk_vision') {
        // 创建弹框form
        createDialogContent(data);
      } else {
        // bkVision工具直接执行
        nextTick(() => {
          if (bkVisionResultRef.value) {
            bkVisionResultRef.value.executeTool();
          }
        });
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

  const handleIamApply = () => {
    if (applyData.value?.apply_url) {
      window.open(applyData.value.apply_url, '_blank');
    }
  };

  const {
    data: applyData,
    run: getApplyData,
  } = useRequest(IamManageService.getApplyData, {
    defaultValue: new IamApplyDataModel(),
  });

  // 点击头部标签(切换工具)
  const handleChangeTool = (TagItem: any) => {
    activeUid.value = TagItem.uid;

    drillDownItemConfig.value = drillDownItem.value?.drill_config
      .find(item => item.tool.uid === activeUid.value)?.config || [];

    fetchToolsDetail({ uid: activeUid.value });
  };

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

  const tagContent = (tags: Array<string>) => {
    const tagNameList = props.tagsEnums.map((i:TagItem) => {
      if (tags.slice(3, tags.length).includes(i.tag_id)) {
        return i.tag_name;
      }
      return null;
    }).filter(e => e !== null);
    return tagNameList.join(',');
  };

  const getToolNameAndType = (uid: string): { name: string, type: string } => {
    const tool = props.allToolsData?.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };

  // 创建单元格渲染函数（公共函数）
  // eslint-disable-next-line max-len
  // const createRenderCell = (fieldItem: OutputFields) =>

  const handleClickDialog = () => {
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

  const submit = () => {
    formRef.value.validate().then(() => {
      formItemRef.value && formItemRef.value.forEach((item: any) => {
        item?.getData();
      });
      // 调用子组件的执行方法
      if (toolDetails.value?.tool_type === 'data_search' && dataSearchResultRef.value) {
        dataSearchResultRef.value.executeTool();
      } else if (toolDetails.value?.tool_type === 'api' && apiSearchResultRef.value) {
        apiSearchResultRef.value.executeTool();
      }
    });
  };

  // 清空表单验证
  const handleReset = () => {
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
  };

  // 获取表单项的默认值
  const getSearchItemDefaultValue = (item: any) => {
    if (item.default_value) {
      return item.default_value;
    }
    if (item.field_category === 'person_select' || item.field_category === 'time_range_select') {
      return [];
    }
    return null;
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

  // 创建弹窗内容
  const createDialogContent = (currentToolDetail: ToolDetailModel) => {
    // 构造form-item
    const createSearchItem = (item: any) => ({
      ...item,
      value: getSearchItemDefaultValue(item),
      required: item.required,
      disabled: props.source === 'risk' && (toolDetails.value?.tool_type === 'data_search' || toolDetails.value?.tool_type === 'api'),
    });

    // 非下钻
    if (!isDrillDownOpen.value) {
      searchList.value = currentToolDetail.config.input_variable.map(createSearchItem);
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
      searchList.value = currentToolDetail.config.input_variable.map((item: any) => {
        const searchItem = createSearchItem(item);
        const configItem = configMap.get(searchItem.raw_name);
        if (!configItem) return searchItem;

        // 动态值处理逻辑
        let dynamicValue = '';
        if (configItem.target_value_type !== 'fixed_value') {
          // 如果target_value是类似'data.risk_id'，则需要把target_value作为json_path
          if (configItem.target_value.includes('.')) {
            dynamicValue = extractDataByPath(drillDownItemRowData.value, configItem.target_value);
          } else if (configItem.target_field_type === 'basic' || !configItem.target_field_type) {
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
      }
    });
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
    handleReset();
    dialogWidth.value = '50%';
    isFullScreen.value = false;
    isShow.value = false;
    emit('close', dialogUid.value);
  };

  watch(() => isFullScreen.value, (val) => {
    nextTick(() => {
      // eslint-disable-next-line no-nested-ternary
      dialogTableHeight.value = val ? (window.innerHeight >= 900 ? `${window.innerHeight * 0.57}px` : '40%') : '300px';
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
