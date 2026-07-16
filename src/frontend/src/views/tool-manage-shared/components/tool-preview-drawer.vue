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
    v-for="(drawer, index) in drawerStack"
    :key="drawer.id"
    v-model:isShow="drawer.isShow"
    :before-close="() => handleDrawerClose(index)"
    ext-cls="tool-preview-sideslider"
    :quick-close="index === drawerStack.length - 1"
    :show-mask="index === drawerStack.length - 1"
    :title="t('工具详情')"
    transfer
    :width="getDrawerWidth(index)"
    :z-index="2000 + index">
    <template #default>
      <div
        v-if="drawer.toolDetails"
        class="preview-drawer-content">
        <!-- 头部工具信息 -->
        <div class="preview-header-info">
          <audit-icon
            class="preview-tool-icon"
            svg
            :type="toolIconMap[drawer.toolDetails.tool_type] || ''" />
          <div class="preview-tool-info">
            <div class="preview-tool-title">
              <span class="preview-tool-name">{{ drawer.toolDetails.name }}</span>
              <bk-tag
                v-for="(tag, tagIndex) in drawer.toolDetails.tags?.slice(0, 3)"
                :key="tagIndex"
                class="desc-tag">
                {{ returnTagsName(tag) }}
              </bk-tag>
              <bk-tag
                v-if="drawer.toolDetails.tags && drawer.toolDetails.tags.length > 3"
                v-bk-tooltips="{
                  content: getTagsTooltipContent(drawer.toolDetails.tags),
                  placement: 'top',
                }"
                class="desc-tag">
                + {{ drawer.toolDetails.tags.length - 3 }}
              </bk-tag>
              <bk-tag
                class="desc-tag desc-tag-info"
                theme="info"
                @click="handleStrategiesClick(drawer.toolDetails)">
                {{ t('运用在') }} {{ drawer.toolDetails.strategies?.length || 0 }} {{ t('个策略中') }}
              </bk-tag>
            </div>
            <div class="preview-tool-desc">
              {{ drawer.toolDetails.description }}
            </div>
          </div>
        </div>
        <tool-content
          :ref="(el: any) => setToolContentRef(el, index)"
          :content-style="{ padding: '0 16px 16px' }"
          :get-tool-name-and-type="getToolNameAndType"
          max-height="calc(100vh - 300px)"
          :search-list="drawer.searchList"
          :tool-details="drawer.toolDetails"
          :uid="drawer.uid"
          @open-field-down="(drillDownItem: any, rowData: Record<string, any>, activeUid?: string) =>
            handleFieldDown(drillDownItem, rowData, activeUid)"
          @update:search-list="(val: any) => drawer.searchList = val" />
      </div>
      <div
        v-else
        class="preview-loading">
        <bk-loading :loading="drawer.isLoading" />
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { nextTick, reactive, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import ToolInfo from '@model/tool/tool-info';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRequest from '@hooks/use-request';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';
  import ToolContent from '@/views/tools/tools-square/components/tool-content.vue';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count?: number;
    icon?: string;
  }

  interface Props {
    tagsEnums: TagItem[];
    allToolsData: ToolInfo[];
  }

  interface DrillDownConfig {
    source_field: string;
    target_value_type: string;
    target_value: string;
    target_field_type?: string;
  }

  interface DrawerItem {
    id: number;
    isShow: boolean;
    isLoading: boolean;
    uid: string;
    toolDetails: ToolDetailModel | null;
    searchList: any[];
    drillConfig?: DrillDownConfig[];
    drillRowData?: Record<string, any>;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const router = useRouter();

  const isShow = defineModel<boolean>('isShow', { default: false });
  // 抽屉栈：支持多层叠加
  const drawerStack = ref<DrawerItem[]>([]);
  const toolContentRefs = ref<Record<number, any>>({});
  let drawerIdCounter = 0;
  const DRILL_DOWN_OFFSET = 200;

  // 根据路径从数据中提取值
  const extractDataByPath = (data: any, path: string): any => {
    if (!path || !data) return null;
    const cleanPath = path.replace(/\[\d+\]/g, '');
    const pathParts = cleanPath.split('.').filter(part => part.length > 0);
    let result = data;
    for (const part of pathParts) {
      if (result === null || result === undefined) return null;
      result = result[part];
    }
    if (typeof result === 'string') {
      result = result.replace(/^["']|["']$/g, '');
    }
    return result;
  };

  // 工具图标映射
  const toolIconMap: Record<string, string> = {
    data_search: 'sqlxiao',
    bk_vision: 'bkvisonxiao',
    api: 'apixiao',
  };

  const setToolContentRef = (el: any, index: number) => {
    if (el) {
      toolContentRefs.value[index] = el;
    }
  };

  const getDrawerWidth = (index: number) => {
    const depth = drawerStack.value.length - 1 - index;
    // depth=0 表示最顶层，使用基础宽度；depth>0 表示被覆盖的层，宽度增加以露出左边缘
    return `calc(100vw - ${1000 - depth * DRILL_DOWN_OFFSET}px)`;
  };

  // 标签名称
  const returnTagsName = (tagId: string) => {
    let tagName = '';
    props.tagsEnums.forEach((item: TagItem) => {
      if (item.tag_id === tagId) {
        tagName = item.tag_name;
      }
    });
    return tagName;
  };

  // 获取标签完整内容（用于 tooltip）
  const getTagsTooltipContent = (tags: string[]) => tags
    .slice(3)
    .map(tagId => returnTagsName(tagId))
    .join('、');

  // 根据uid获取工具名称和类型（用于下钻）
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

  // 策略跳转
  const handleStrategiesClick = (item: any) => {
    if (!item?.strategies?.length) return;
    const sceneParams = getSceneSystemParams();
    const query: Record<string, string> = {
      strategy_id: item.strategies.join(','),
    };
    // 携带场景信息
    if (sceneParams.scope_id) {
      query.scene_id = sceneParams.scope_id;
      query.scope_id = sceneParams.scope_id;
      query.scope_type = sceneParams.scope_type;
    } else if (sceneParams.scope_type) {
      query.scope_type = sceneParams.scope_type;
    }
    const url = router.resolve({
      name: 'strategyList',
      query,
    }).href;
    window.open(url, '_blank');
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

  // 判断字段是否有有效值
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

  const createDialogContent = (currentToolDetail: ToolDetailModel, drawerIndex: number) => {
    const createSearchItem = (item: any) => ({
      ...item,
      value: getSearchItemDefaultValue(item),
      required: item.required,
      disabled: false,
    });

    const drawer = drawerStack.value[drawerIndex];
    if (!drawer) return;

    const { drillConfig, drillRowData } = drawer;

    if (drillConfig && drillConfig.length > 0 && drillRowData) {
      // 下钻模式：根据 drill_config 自动填充参数
      const configMap = new Map<string, DrillDownConfig>();
      drillConfig.forEach((configItem) => {
        configMap.set(configItem.source_field, configItem);
      });

      drawer.searchList = (currentToolDetail.config?.input_variable || []).map((item: any) => {
        const searchItem = createSearchItem(item);
        const configItem = configMap.get(searchItem.raw_name);
        if (!configItem) return searchItem;

        let dynamicValue: any = '';
        if (configItem.target_value_type !== 'fixed_value') {
          if (configItem.target_value.includes('.')) {
            dynamicValue = extractDataByPath(drillRowData, configItem.target_value);
          } else if (configItem.target_field_type === 'basic' || !configItem.target_field_type) {
            dynamicValue = drillRowData?.[configItem.target_value] ?? searchItem.value;
          } else {
            dynamicValue = drillRowData?.event_data?.[configItem.target_value] ?? searchItem.value;
          }
        }

        return {
          ...searchItem,
          value: configItem.target_value_type === 'fixed_value'
            ? configItem.target_value
            : dynamicValue,
        };
      });
    } else {
      // 非下钻模式：使用默认值
      drawer.searchList = currentToolDetail.config.input_variable.map(createSearchItem);
    }

    nextTick(() => {
      const toolContentRef = toolContentRefs.value[drawerIndex];
      if (toolContentRef) {
        toolContentRef.setFormItemData(drawer.searchList);
        // 下钻模式或所有必填字段都有值时，自动查询
        const shouldAutoSubmit = (drillConfig && drillConfig.length > 0) || drawer.searchList.every(validateField);
        if (shouldAutoSubmit) {
          nextTick(() => {
            toolContentRef.submit();
          });
        }
      }
    });
  };

  // 获取工具详情
  const {
    run: fetchToolDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      // 找到对应的抽屉层并更新数据
      const drawerIndex = drawerStack.value.findIndex(d => d.uid === data.uid && d.isLoading);
      if (drawerIndex === -1) return;

      const drawer = drawerStack.value[drawerIndex];
      drawer.toolDetails = data;
      drawer.isLoading = false;

      if (data.tool_type !== 'bk_vision') {
        createDialogContent(data, drawerIndex);
      } else {
        nextTick(() => {
          const toolContentRef = toolContentRefs.value[drawerIndex];
          if (toolContentRef) {
            toolContentRef.executeBkVision();
          }
        });
      }
    },
  });

  const handleFieldDown = (
    drillDownItem: any,
    drillDownItemRowData: Record<string, any>,
    activeUid?: string,
  ) => {
    const targetUid = activeUid
      || drillDownItem?.drill_config?.[0]?.tool?.uid;
    if (!targetUid) return;

    // 获取对应的 drill_config
    const drillConfig = drillDownItem?.drill_config?.find((c: any) => c.tool.uid === targetUid)?.config || [];

    // 创建新的抽屉层，携带下钻参数
    drawerIdCounter += 1;
    const newDrawer: DrawerItem = reactive({
      id: drawerIdCounter,
      isShow: true,
      isLoading: true,
      uid: targetUid,
      toolDetails: null,
      searchList: [],
      drillConfig,
      drillRowData: drillDownItemRowData,
    });

    drawerStack.value.push(newDrawer);
    fetchToolDetail({ uid: targetUid });
  };

  // 关闭指定层的抽屉
  const handleDrawerClose = (index: number) => {
    // 关闭该层及其上方所有抽屉
    drawerStack.value.splice(index);
    // 清理对应的组件引用
    Object.keys(toolContentRefs.value).forEach((key) => {
      if (Number(key) >= index) {
        delete toolContentRefs.value[Number(key)];
      }
    });

    if (drawerStack.value.length === 0) {
      isShow.value = false;
    }
    return true;
  };

  // 监听外部 isShow 变化（关闭时清空所有抽屉）
  watch(isShow, (val) => {
    if (!val) {
      drawerStack.value = [];
      toolContentRefs.value = {};
    }
  });

  // 暴露打开预览的方法
  const open = (uid: string) => {
    // 清空之前的抽屉栈
    drawerStack.value = [];
    toolContentRefs.value = {};
    isShow.value = true;

    // 创建第一层抽屉
    drawerIdCounter += 1;
    const firstDrawer: DrawerItem = reactive({
      id: drawerIdCounter,
      isShow: true,
      isLoading: true,
      uid,
      toolDetails: null,
      searchList: [],
    });

    drawerStack.value.push(firstDrawer);
    fetchToolDetail({ uid });
  };

  defineExpose({ open });
</script>

<style lang="postcss" scoped>
  .preview-drawer-content {
    min-height: 100%;
    padding: 0;
    background: #f5f7fa;

    :deep(.top-search) {
      border-radius: 4px;
    }
  }

  .preview-header-info {
    display: flex;
    padding: 16px 24px;
    background: #fff;

    .preview-tool-icon {
      width: 48px;
      height: 48px;
      border-radius: 4px;
    }

    .preview-tool-info {
      margin-left: 8px;

      .preview-tool-title {
        display: flex;
        align-items: center;
        font-size: 16px;
        font-weight: 700;
        line-height: 24px;
        color: #313238;

        .preview-tool-name {
          max-width: 300px;
          margin-right: 5px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .desc-tag {
          margin-right: 5px;
          font-size: 12px;
          font-weight: 500;
          line-height: 22px;
          color: #4d4f56;
        }

        .desc-tag-info {
          color: #1768ef;
          cursor: pointer;
        }
      }

      .preview-tool-desc {
        margin-top: 4px;
        font-size: 14px;
        line-height: 22px;
        color: #313238;
      }
    }
  }

  .preview-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
  }
</style>

<style lang="postcss">
  /* 覆盖抽屉内容区域背景色，确保灰色铺满 */
  .tool-preview-sideslider .bk-modal-body {
    background: #f5f7fa;
  }

  .tool-preview-sideslider .bk-modal-content {
    height: 100%;
  }

  .tool-preview-sideslider.bk-sideslider-content {
    height: 100%;
  }

  .tool-preview-sideslider .bk-modal-wrapper {
    transition: width .3s ease-in-out;
  }


</style>
