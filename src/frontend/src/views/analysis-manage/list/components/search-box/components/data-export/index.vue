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
    v-model:is-show="isShow"
    quick-close
    :title="t('审计日志导出')">
    <div class="export-data-overview">
      <div class="export-data-overview-item">
        <div class="count">
          {{ total }}
        </div>
        <div class="describe">
          {{ t('当前数据量级') }}
        </div>
      </div>
      <div class="export-data-overview-item">
        <div class="count">
          {{ Math.ceil((total / 20) / 60) }}min
        </div>
        <div class="describe">
          {{ t('预计下载用时') }}
        </div>
      </div>
    </div>
    <div class="export-data-range">
      {{ t('导出范围') }}
    </div>
    <bk-radio-group
      v-model="exportRange"
      class="export-data-range-radio">
      <bk-radio
        label="all">
        {{ t('全部字段') }}
      </bk-radio>
      <bk-radio
        label="standard">
        {{ t('标准字段') }}
        <audit-icon
          v-bk-tooltips="t('系统上报的审计标准字段')"
          style="margin-left: 4px; color: #c4c6cc; cursor: pointer;"
          type="help-fill" />
      </bk-radio>
      <bk-radio
        label="specified">
        {{ t('指定字段') }}
      </bk-radio>
    </bk-radio-group>
    <template v-if="exportRange === 'specified'">
      <bk-popover
        ext-cls="data-export-popover"
        :is-show="isShowCascader"
        placement="bottom-start"
        style="padding: 0;"
        theme="light"
        trigger="click"
        @after-hidden="handleAfterHidden">
        <bk-tag-input
          v-model="tags"
          allow-auto-match
          allow-create
          clearable
          :list="[]"
          placeholder="输入关键字搜索"
          @input="handleInput" />
        <template #content>
          <field-cascader
            v-model="selectedItems"
            :data="data"
            :is-searching="isSearching"
            :search-keyword="searchKeyword"
            @clear-search="handleClearSearch"
            @select="handleSelect" />
        </template>
      </bk-popover>
    </template>
    <template #footer>
      <bk-button
        class="mr8"
        :disabled="!fields.length && exportRange === 'specified'"
        theme="primary"
        @click="handleConfirmSearch">
        {{ t('确定') }}
      </bk-button>
      <bk-button @click="handleClosed">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>

<script setup lang="ts">
  import { inject, type Ref, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import FieldCascader from '../field-cascader/index.vue';

  import useDebouncedRef from '@/hooks/use-debounced-ref';
  import useRequest from '@/hooks/use-request';

  interface CascaderItem {
    id: string
    name: string
    disabled: boolean
    children: CascaderItem[]
    isJson: boolean
    allow_operators: string[]
    dynamic_content: boolean
    level: number
  }

  interface Props {
    data: CascaderItem[];
    modelValue?: Record<string, boolean>;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const isShow = defineModel<boolean>('isShow', {
    required: true,
  });

  const total = inject <Ref<number>>('total', ref(0));
  const exportRange = ref('all');
  const tableSearchModel = inject <Ref<Record<string, any>>>('tableSearchModel', ref({}));

  const selectedItems = ref<Record<string, boolean>>({});

  const tags = ref<Array<string>>([]);
  const isShowCascader = ref(false);

  const fields = ref<Array<{
    keys: string[];
    raw_name: string;
    display_name: string;
  }>>([]);
  const list = ref<Array<CascaderItem>>([]);

  const searchKeyword = useDebouncedRef('');
  const isSearching = ref(false);

  const renderPanels = ref<Array<{
    parent: CascaderItem | null;
    data: CascaderItem[];
  }>>([]);

  // 创建导出任务
  const {
    run: createQueryTask,
  } = useRequest(EsQueryService.createQueryTask, {
    defaultValue: {},
  });

  // 弹出层隐藏后的处理
  const handleAfterHidden = (value: { isShow: boolean}) => {
    isShowCascader.value = value.isShow;
    if (!value.isShow) {
      // 重置面板状态，只保留第一级
      renderPanels.value = [{
        parent: null,
        data: list.value,
      }];
      searchKeyword.value = '';
      isSearching.value = false;
    }
  };

  const handleClosed = () => {
    isShow.value = false;
    exportRange.value = 'all';
    fields.value = [];
  };

  // 处理选择事件
  const handleSelect = (item: CascaderItem, isChecked: boolean) => {
    const fieldId = item.id;
    let fieldKeys: string[] = [];
    let rawName = fieldId;
    const displayName = item.name;

    // 尝试解析 ID，检查是否为数组字符串
    try {
      const parsedId = JSON.parse(fieldId);
      if (Array.isArray(parsedId) && parsedId.length > 0) {
        // eslint-disable-next-line prefer-destructuring
        rawName = parsedId[0];
        fieldKeys = parsedId.slice(1);
      }
    } catch (e) {
      // 如果解析失败，说明不是JSON字符串，使用默认值
      rawName = fieldId;
      fieldKeys = [];
    }

    const fieldInfo = {
      keys: fieldKeys,
      raw_name: rawName,
      display_name: displayName,
    };

    if (isChecked) {
      // 如果是选中，添加到字段列表（避免重复添加）
      if (!fields.value.some(field => field.raw_name === fieldInfo.raw_name
        && JSON.stringify(field.keys) === JSON.stringify(fieldInfo.keys))) {
        fields.value.push(fieldInfo);
      }
      if (!tags.value.some(tag => tag === displayName)) {
        tags.value.push(displayName);
      }
    } else {
      // 如果是取消选中，从字段列表中移除
      fields.value = fields.value.filter(field => field.raw_name !== fieldInfo.raw_name
        || JSON.stringify(field.keys) !== JSON.stringify(fieldInfo.keys));
      // 删除tags逻辑
      tags.value = tags.value.filter(tag => tag !== displayName);
    }
    console.log('tags', tags.value);
  };

  const handleClearSearch = () => {
    searchKeyword.value = '';
    isSearching.value = false;
  };

  const handleConfirmSearch = () => {
    const params = {
      query_params: tableSearchModel.value,
      export_config: {
        field_scope: exportRange.value,
        fields: fields.value,
      },
    };
    createQueryTask(params);
  };

  const handleInput = (value: string) => {
    console.log('value', value);
    searchKeyword.value = value;
    isSearching.value = true;
  };

  // 同步外部值的改动
  watch(() => props.modelValue, (newVal) => {
    selectedItems.value = { ...newVal };
  }, {
    immediate: true,
  });

  // 监听搜索关键词变化
  watch(() => searchKeyword.value, (newVal) => {
    isSearching.value = !!newVal;
  });

</script>
<style lang="postcss" scoped>
.export-data-overview {
  display: flex;
  padding: 15px 0;
  margin: 20px 0;
  background-color: #f5f7fa;
  justify-content: space-around;

  .export-data-overview-item {
    text-align: center;

    .count {
      font-size: 20px;
      font-weight: 700;
    }

    .describe {
      font-size: 12px;
    }
  }
}

.export-data-range {
  margin-bottom: 10px;
  font-weight: 700;
}

:deep(.export-data-range-radio) {
  margin-bottom: 15px;

  .bk-radio-input {
    width: 14px;
    height: 14px
  }

  .bk-radio-label {
    font-size: 12px;
  }
}
</style>
<style lang="postcss">
.data-export-popover {
  .bk-pop2-arrow {
    display: none;
  }

  .audit-field-cascader {
    height: 300px !important;

    .audit-field-cascader-panel.audit-field-cascader-panel-child {
      height: 300px !important;
      transform: translateY(0) !important;
    }
  }
}
</style>
