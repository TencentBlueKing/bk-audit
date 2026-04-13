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
    v-model:isShow="isShow"
    quick-close
    :title="t('工具详情')"
    transfer
    width="calc(100vw - 300px)">
    <template #default>
      <div
        v-if="toolDetails"
        class="preview-drawer-content">
        <!-- 头部工具信息 -->
        <div class="preview-header-info">
          <audit-icon
            class="preview-tool-icon"
            svg
            :type="toolIconMap[toolDetails.tool_type] || ''" />
          <div class="preview-tool-info">
            <div class="preview-tool-title">
              <span class="preview-tool-name">{{ toolDetails.name }}</span>
              <bk-tag
                v-for="(tag, tagIndex) in toolDetails.tags?.slice(0, 3)"
                :key="tagIndex"
                class="desc-tag">
                {{ returnTagsName(tag) }}
              </bk-tag>
              <bk-tag
                v-if="toolDetails.tags && toolDetails.tags.length > 3"
                v-bk-tooltips="{
                  content: getTagsTooltipContent(toolDetails.tags),
                  placement: 'top',
                }"
                class="desc-tag">
                + {{ toolDetails.tags.length - 3 }}
              </bk-tag>
              <bk-tag
                class="desc-tag desc-tag-info"
                theme="info"
                @click="handleStrategiesClick(toolDetails)">
                {{ t('运用在') }} {{ toolDetails.strategies?.length || 0 }} {{ t('个策略中') }}
              </bk-tag>
            </div>
            <div class="preview-tool-desc">
              {{ toolDetails.description }}
            </div>
          </div>
        </div>
        <!-- 工具内容区域（复用工具广场组件） -->
        <tool-content
          ref="toolContentRef"
          :content-style="{ padding: '0 16px 16px' }"
          :get-tool-name-and-type="getToolNameAndType"
          max-height="calc(100vh - 300px)"
          :search-list="searchList"
          :tool-details="toolDetails"
          :uid="currentUid"
          @open-field-down="handleFieldDown"
          @update:search-list="(val: any) => searchList = val" />
      </div>
      <div
        v-else
        class="preview-loading">
        <bk-loading :loading="isLoading" />
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import ToolManageService from '@service/tool-manage';

  import ToolDetailModel from '@model/tool/tool-detail';

  import useRequest from '@hooks/use-request';

  import ToolContent from '@/views/tools/tools-square/components/tool-content.vue';

  interface TagItem {
    tag_id: string;
    tag_name: string;
    tool_count: number;
    icon?: string;
  }

  interface Props {
    tagsEnums: TagItem[];
    allToolsData: ToolDetailModel[];
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const router = useRouter();

  const isShow = defineModel<boolean>('isShow', { default: false });
  const isLoading = ref(false);
  const currentUid = ref('');
  const toolDetails = ref<ToolDetailModel | null>(null);
  const searchList = ref<any[]>([]);
  const toolContentRef = ref();

  // 工具图标映射
  const toolIconMap: Record<string, string> = {
    data_search: 'sqlxiao',
    bk_vision: 'bkvisonxiao',
    api: 'apixiao',
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
    const url = router.resolve({
      name: 'strategyList',
      query: {
        strategy_id: item.strategies.join(','),
      },
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

  // 创建抽屉内容（构造表单）
  const createDialogContent = (currentToolDetail: ToolDetailModel) => {
    const createSearchItem = (item: any) => ({
      ...item,
      value: getSearchItemDefaultValue(item),
      required: item.required,
      disabled: false,
    });
    searchList.value = currentToolDetail.config.input_variable.map(createSearchItem);

    nextTick(() => {
      if (toolContentRef.value) {
        toolContentRef.value.setFormItemData(searchList.value);

        // 如果所有必填字段都有值，则自动查询
        nextTick(() => {
          const isValid = searchList.value.every(validateField);
          if (isValid) {
            toolContentRef.value.submit();
          }
        });
      }
    });
  };

  // 获取工具详情
  const {
    run: fetchToolDetail,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      toolDetails.value = data;
      currentUid.value = data.uid;
      isLoading.value = false;

      if (data.tool_type !== 'bk_vision') {
        createDialogContent(data);
      } else {
        nextTick(() => {
          if (toolContentRef.value) {
            toolContentRef.value.executeBkVision();
          }
        });
      }
    },
  });

  // 下钻字段点击处理
  const handleFieldDown = (
    drillDownItem: any,
    _drillDownItemRowData: Record<string, any>,
    activeUid?: string,
  ) => {
    const targetUid = activeUid
      || drillDownItem?.drill_config?.[0]?.tool?.uid;
    if (!targetUid) return;

    isLoading.value = true;
    toolDetails.value = null;
    searchList.value = [];
    currentUid.value = targetUid;
    fetchToolDetail({ uid: targetUid });
  };

  // 关闭时重置状态
  watch(isShow, (val) => {
    if (!val) {
      toolDetails.value = null;
      searchList.value = [];
      currentUid.value = '';
    }
  });

  // 暴露打开预览的方法
  const open = (uid: string) => {
    isShow.value = true;
    isLoading.value = true;
    toolDetails.value = null;
    searchList.value = [];
    currentUid.value = uid;
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
  .bk-sideslider .bk-modal-body {
    background: #f5f7fa;
  }

  .bk-sideslider .bk-modal-content {
    height: 100%;
  }

  .bk-sideslider .bk-sideslider-content {
    height: 100%;
  }
</style>
