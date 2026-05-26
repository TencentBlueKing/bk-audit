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
  <div
    class="scene-table-wrapper"
    :class="[{ 'scene-table-section': !!title }]">
    <!-- 标题 + 搜索框 -->
    <div
      v-if="title || enableSearch"
      class="scene-table-header">
      <div
        v-if="title"
        class="section-title">
        {{ title }}
        <bk-popover
          v-if="tooltip"
          :max-width="400"
          placement="top"
          theme="dark">
          <span style="display: inline-flex; align-items: center; width: 14px; height: 14px;">
            <audit-icon
              class="info-icon"
              type="info-fill" />
          </span>
          <template #content>
            <div>{{ tooltip }}</div>
          </template>
        </bk-popover>
      </div>
      <bk-search-select
        v-if="enableSearch"
        v-model="searchKeyword"
        class="scene-table-search"
        clearable
        :data="searchData"
        :defaut-using-item="{ inputHtml: t('请选择') }"
        :get-menu-list="getMenuList"
        :placeholder="searchPlaceholder || t('请输入关键字搜索')"
        unique-select />
    </div>
    <!-- PrimaryTable 表格 -->
    <primary-table
      :columns="columns"
      :data="pageData"
      :max-height="maxHeight"
      :resizable="resizable"
      row-key="id"
      :stripe="stripe"
      :style="{ '--row-height': rowHeight + 'px' }" />
    <!-- 分页器 -->
    <div
      v-if="showPagination && filteredData.length > 0"
      class="scene-table-pagination">
      <bk-pagination
        v-model="currentPage"
        align="left"
        :count="filteredData.length"
        :layout="['total', 'limit', 'list']"
        :limit="currentLimit"
        :limit-list="limitList"
        location="left"
        @change="handlePageChange"
        @limit-change="handleLimitChange" />
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { PrimaryTable } from '@blueking/tdesign-ui';
  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  import '@blueking/tdesign-ui/vue3/index.css';

  interface SearchDataItem {
    id: string;
    name: string;
    placeholder?: string;
    children?: Array<{ id: string; name: string }>;
    /** 过滤时使用的字段 key，默认与 id 同名 */
    field?: string;
    /** 自定义匹配函数（可选） */
    match?: (row: Record<string, any>, keyword: string) => boolean;
  }

  interface Props {
    columns: Array<Record<string, any>>;
    data: Array<Record<string, any>>;
    maxHeight?: number | string;
    showPagination?: boolean;
    limit?: number;
    limitList?: number[];
    title?: string;
    tooltip?: string;
    resizable?: boolean;
    stripe?: boolean;
    rowHeight?: number;
    enableSearch?: boolean;
    searchData?: SearchDataItem[];
    searchPlaceholder?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    maxHeight: undefined,
    showPagination: false,
    limit: 10,
    limitList: () => [10, 20, 50, 100, 1000],
    title: '',
    tooltip: '',
    resizable: false,
    stripe: true,
    rowHeight: 36,
    enableSearch: false,
    searchData: () => [],
    searchPlaceholder: '',
  });

  const { t } = useI18n();

  // 获取用户列表（用于远程搜索人员字段）
  const {
    run: fetchUserList,
  } = useRequest(MetaManageService.fetchUserList, {
    defaultParams: { page: 1, page_size: 30 },
    defaultValue: { count: 0, results: [] } as { count: number; results: any[] },
  });

  // 需要远程搜索的用户字段 id 列表
  const userSearchFieldIds = computed(() => props.searchData
    .filter(item => item.children !== undefined)
    .map(item => item.id));

  // 远程搜索菜单列表（管理员等人员字段输入时实时搜索）
  const getMenuList = async (item: any, keyword: string) => {
    if (!item) return props.searchData;
    if (userSearchFieldIds.value.includes(item.id) && keyword) {
      const userList = await fetchUserList({ fuzzy_lookups: keyword });
      return userList.results.map((u: any) => ({
        id: u.username,
        name: `${u.username}(${u.display_name})`,
      }));
    }
    return [];
  };

  const currentPage = ref(1);
  const currentLimit = ref(props.limit);
  const searchKeyword = ref<any[]>([]);

  // 监听 limit prop 变化
  watch(() => props.limit, (val) => {
    currentLimit.value = val;
  });

  // 当数据变化时重置页码
  watch(() => props.data, () => {
    currentPage.value = 1;
  });

  // 搜索条件变化时重置页码
  watch(searchKeyword, () => {
    currentPage.value = 1;
  }, { deep: true });

  // 搜索过滤
  const filteredData = computed(() => {
    if (!props.enableSearch || !searchKeyword.value || searchKeyword.value.length === 0) {
      return props.data;
    }
    const searchDataMap = new Map<string, SearchDataItem>();
    props.searchData.forEach((item) => {
      searchDataMap.set(item.id, item);
    });
    return props.data.filter((row) => {
      // 用 JSON.stringify 将整行序列化为字符串，确保兼容 Vue Proxy 响应式对象
      // 预计算：避免每个关键字重复序列化
      const rowJsonStr = JSON.stringify(row).toLowerCase();
      return searchKeyword.value.every((cond) => {
        const cfg = searchDataMap.get(cond.id);
        const isRemoteUserField = !!cfg?.children;
        // 远程搜索人员字段用 v.id（纯 username），其他字段用 v.name
        const keywords = (cond.values || []).map((v: any) => {
          if (isRemoteUserField) return v.id || '';
          return v.name || v.id;
        }).filter(Boolean);
        // 自由输入：cond.id 本身就是关键字
        const freeKeyword = (!cond.values || cond.values.length === 0) ? cond.id : '';
        const matchKeywords = freeKeyword ? [freeKeyword] : keywords;
        if (matchKeywords.length === 0) return true;

        // 自定义匹配函数优先
        if (cfg?.match) {
          return matchKeywords.some((kw: string) => cfg.match!(row, kw));
        }

        // 全行 JSON 匹配：兼容所有数据类型（数组、Proxy、嵌套对象）
        return matchKeywords.some((kw: string) => rowJsonStr.includes(kw.toLowerCase()));
      });
    });
  });

  // 计算当前页数据
  const pageData = computed(() => {
    if (!props.showPagination) {
      return filteredData.value;
    }
    const start = (currentPage.value - 1) * currentLimit.value;
    return filteredData.value.slice(start, start + currentLimit.value);
  });

  const handlePageChange = (page: number) => {
    currentPage.value = page;
  };

  const handleLimitChange = (limit: number) => {
    currentLimit.value = limit;
    currentPage.value = 1;
  };
</script>

<style lang="postcss" scoped>
  .scene-table-wrapper {
    width: 100%;
  }

  /* 作为独立区块时的样式（带标题） */
  .scene-table-section {
    padding: 16px 24px 24px;
    margin-bottom: 24px;
    background-color: #fff;
    border-radius: 2px;
  }

  .scene-table-header {
    display: flex;
    flex-wrap: nowrap;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .scene-table-search {
    width: 600px;
    margin-left: auto;
  }

  .section-title {
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    align-items: center;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .info-icon {
    flex-shrink: 0;
    font-size: 14px;
    color: #c4c6cc;
    cursor: pointer;
  }

  /* 时间标签 */
  :deep(.time-label) {
    display: inline-block;
    padding: 0 6px;
    font-size: 12px;
    line-height: 20px;
    border-radius: 2px;
  }

  :deep(.time-label-danger) {
    color: #ea3636;
    background-color: #feebea;
  }

  :deep(.time-label-warning) {
    color: #ff9c01;
    background-color: #fff3e1;
  }

  :deep(.time-label-success) {
    color: #2dcb56;
    background-color: #e5f6ea;
  }

  :deep(.domain-cell) {
    display: inline-flex;
    align-items: center;

    .domain-text {
      color: #313238;
    }

    .domain-jump-icon {
      display: none;
      align-items: center;
      margin-left: 4px;
      font-size: 15px;
      color: #3a84ff;
      cursor: pointer;
    }

    &:hover .domain-jump-icon {
      display: inline-flex;
    }
  }

  :deep(.ml8) {
    margin-left: 8px;
  }

  /* 可用字段下划线链接 */
  :deep(.field-count-link) {
    color: #313238;
    cursor: pointer;
    border-bottom: 1px dashed #c4c6cc;

    &:hover {
      color: #3a84ff;
      border-bottom-color: #3a84ff;
    }
  }

  /* 可用字段气泡窗内容 */
  :deep(.field-popover-content) {
    max-height: 500px;
  }

  /* PrimaryTable 表格样式 */
  :deep(.t-table) {
    table {
      table-layout: fixed !important;
    }

    /* TDesign ellipsis 样式（tdesign-vue-next 原生 CSS 未被引入时需要手动补充） */
    .t-text-ellipsis {
      overflow: hidden;
      line-height: 22px;
      text-overflow: ellipsis;
      word-wrap: normal;
      white-space: nowrap;
    }

    th,
    td {
      height: var(--row-height, 36px) !important;
      border-right: none !important;
      border-left: none !important;
    }

    /* 表头行 */
    thead tr {
      background-color: #f5f7fa !important;
      border-bottom: 1px solid #dcdee5 !important;
    }

    /* 内容行 */
    tbody tr:nth-child(even) {
      background-color: #fafbfd !important;
    }

    tbody tr:nth-child(odd) {
      background-color: #fff !important;
    }
  }

  /* 分页器样式（使用 bk-pagination 内置 layout: total/limit/list） */
  .scene-table-pagination {
    padding: 12px 0 0;

    :deep(.bk-pagination) {
      .is-last {
        margin-left: auto;
      }
    }
  }
</style>
