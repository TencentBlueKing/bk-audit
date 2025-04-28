<template>
  <skeleton-loading
    fullscreen
    :loading="false"
    name="strategyList">
    <div class="link-data-manage">
      <!-- 左侧标签-->
      <render-label
        ref="renderLabelRef"
        :labels="linkDataLabelList"
        :total="total"
        @change="handleLeftWidth"
        @checked="handleChecked" />


      <!-- 右侧表格 -->
      <div
        class="link-data-manage-list"
        :style="styles">
        <div class="action-header">
          <bk-button
            class="w88"
            theme="primary"
            @click="handleCreate">
            {{ t('新建联表') }}
          </bk-button>
          <bk-search-select
            v-model="searchKey"
            class="search-input"
            clearable
            :condition="[]"
            :data="searchData"
            :defaut-using-item="{ inputHtml: t('请选择') }"
            :placeholder="t('联表id、联表数据名称、最近更新人、标签')"
            unique-select
            :validate-values="validateValues"
            value-split-code=","
            @update:model-value="handleSearch" />
        </div>
        <render-list
          ref="listRef"
          class="audit-highlight-table"
          :columns="tableColumn"
          :data-source="dataSource"
          :settings="settings"
          @clear-search="handleClearSearch"
          @on-setting-change="handleSettingChange"
          @request-success="handleRequestSuccess" />
      </div>
    </div>
  </skeleton-loading>
  <create-link-data
    ref="createRef"
    @show-link-strategy="handleShowLinkStrategy"
    @update="handleCreateUpdate" />
  <link-data-detail
    ref="detailRef"
    :max-version-map="maxVersionMap" />
</template>
<script setup lang="tsx">
  import { InfoBox } from 'bkui-vue';
  import _ from 'lodash';
  import { computed, h, onMounted, ref, shallowRef } from 'vue';
  import { useI18n } from 'vue-i18n';

  import LinkDataManageService from '@service/link-data-manage';

  import LinkDataModel from '@model/link-data/link-data';

  import useRecordPage from '@hooks/use-record-page';
  import useUrlSearch from '@hooks/use-url-search';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import CreateLinkData from '../link-data-create/index.vue';
  import LinkDataDetail from '../link-data-detail/index.vue';

  import RenderLabel from './components/render-label.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface SearchData{
    name: string;
    id: string;
    children?: Array<SearchData>;
    placeholder?: string;
    multiple?: boolean;
    onlyRecommendChildren?: boolean,
  }
  interface SearchKey {
    id: string,
    name: string,
    values: [
      {
        id: string,
        name: string
      }
    ]
  }
  interface Arrays {
    id: number | string,
    name: string
  }
  interface LinkData {
    page: number;
    num_pages: number;
    total: number;
    results: Array<LinkDataModel>
  }
  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const {
    getSearchParams,
  } = useUrlSearch();
  const {
    getRecordPageParams,
  } = useRecordPage;
  const listRef = ref();
  const createRef = ref();
  const detailRef = ref();
  const renderLabelRef = ref();
  const isNeedShowDetail = ref(false);

  const validateValues = async (item: Record<string, any>, value: Array<Arrays>) => {
    if (item && item.id === 'tags') {
      const tag = value[0].id;
      return strategyTagMap.value[tag] ? true : t('该标签不存在');
    }
    return true;
  };

  const dataSource = LinkDataManageService.fetchStrategyList;
  const defaultSearchData = [
    {
      name: t('联表id'),
      id: 'uid',
      placeholder: t('请输入联表id'),
    },
    {
      name: t('联表数据名称'),
      id: 'name__contains',
      placeholder: t('请输入联表数据名称'),
    },
    {
      name: t('最近更新人'),
      id: 'updated_by',
      placeholder: t('请输入最近更新人'),
      onlyRecommendChildren: true,
    },
  ];
  let searchData: SearchData[] = [
    ... defaultSearchData,
    {
      name: t('标签'),
      id: 'tags',
      placeholder: t('请选择状态'),
      onlyRecommendChildren: true,
    },
  ];

  const linkDataLabelList = ref<Array<{
    link_table_count: number,
    tag_id: string,
    tag_name: string
  }>>([]);
  const strategyTagMap = ref<Record<string, string>>({});
  const total = ref(0);
  const searchKey = ref<Array<SearchKey>>([]);
  const leftLabelFilterCondition = ref('');
  const maxVersionMap = ref<Record<string, number>>({});
  const tableColumn = ref([
    {
      label: () => t('联表数据名称'),
      sort: 'custom',
      field: () => 'name' as string,
      render: ({ data }: { data: LinkDataModel}) => <a onClick={() => handleDetail(data)}>
          <Tooltips data={data.name} />
        </a>
      ,
    },
    {
      label: () => t('标签'),
      field: () => 'tags',
      width: 230,
      render: ({ data }: { data: LinkDataModel }) => {
        const tags = data.tags.map(item => strategyTagMap.value[item] || item);
        return <EditTag data={tags} key={data.id} />;
      },
    },
    {
      label: () => t('关联策略'),
      width: 100,
      field: () => 'strategy_count',
      render: ({ data }: { data: LinkDataModel}) => (data.strategy_count ? <bk-badge
          class='edit-badge'
          position="top-right"
          theme="danger"
          visible={!data.need_update_strategy}
          dot
      >
        <a
          v-bk-tooltips={{
            content: t('策略使用的方案，有新版本待升级'),
            disabled: !data.need_update_strategy,
          }}
          onClick={() => handleLinkStrategy(data)}>
          {data.strategy_count}
        </a>
      </bk-badge> : <div>{data.strategy_count}</div>),
    },
    {
      label: () => t('最近更新人'),
      sort: 'custom',
      field: () => 'updated_by',
    },
    {
      label: () => t('最近更新时间'),
      sort: 'custom',
      field: () => 'updated_at',
    },
    {
      label: () => t('创建人'),
      sort: 'custom',
      field: () => 'created_by',
    },
    {
      label: () => t('创建时间'),
      sort: 'custom',
      field: () => 'created_at',
    },
    {
      label: () => t('操作'),
      width: '160px',
      fixed: 'right',
      render: ({ data }: {data: LinkDataModel}) => (
      <>
        <auth-button
          permission={data.permission.edit_link_table}
          actionId="edit_link_table"
          text
          class='mr16'
          theme="primary"
          onClick={() => handleEdit(data)}>
          { t('编辑') }
        </auth-button>
        <auth-button
          permission={data.permission.delete_link_table}
          actionId="delete_link_table"
          v-bk-tooltips={{
            content: t('已有策略在使用，不可删除'),
            disabled: data.strategy_count <= 0,
          }}
          text
          disabled={data.strategy_count > 0}
          theme="primary"
          onClick={() => handleDelete(data)}>
          { t('删除') }
        </auth-button>
      </>
      ),
    }]);

  const styles = shallowRef({ left: '216px' });
  const disabledMap: Record<string, string> = {
    name: 'name',
    tags: 'tags',
    strategy_count: 'strategy_count',
    updated_by: 'updated_by',
    updated_at: 'updated_at',
  };
  const initSettings = () => ({
    fields: tableColumn.value.reduce((res, item) => {
      if (item.field) {
        res.push({
          label: item.label(),
          field: item.field(),
          disabled: !!disabledMap[item.field()],
        });
      }
      return res;
    }, [] as Array<{
      label: string, field: string, disabled: boolean,
    }>),
    checked: ['name', 'tags', 'strategy_count', 'updated_by', 'updated_at'],
    showLineHeight: false,
  });
  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-link-data-manage-list-setting');
    if (jsonStr) {
      const jsonSetting = JSON.parse(jsonStr);
      jsonSetting.showLineHeight = false;
      return jsonSetting;
    }
    return initSettings();
  });

  // 删除
  const {
    run: deleteLinkData,
  } = useRequest(LinkDataManageService.deleteLinkData, {
    defaultValue: {},
    onSuccess: () => {
      listRef.value.refreshList();
      messageSuccess(t('删除成功'));
    },
  });

  // 获取标签列表
  const {
    run: fetchLinkTableTags,
  } = useRequest(LinkDataManageService.fetchLinkTableTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
      });
      linkDataLabelList.value = data;
    },
  });

  // 获取全部联表
  const {
    run: fetchLinkTableAll,
  } = useRequest(LinkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      maxVersionMap.value = data.reduce((res, item) => {
        res[item.uid] = item.version;
        return res;
      }, {} as Record<string, number>);
    },
  });

  // 搜索
  const handleSearch = (keyword: Array<any>) => {
    const search = {
      uid: '',
      name__contains: '',
      tags: '',
      updated_by: '',
    } as Record<string, any>;

    keyword.forEach((item: SearchKey, index) => {
      if (item.values) {
        const value = item.values.map(item => item.id).join(',');
        search[item.id] = value;
      } else {
        const list = search.name__contains.split(',').filter((item: string) => !!item);
        list.push(item.id);
        _.uniq(list);
        search.name__contains = list.join(',');
        searchKey.value[index] = ({ id: 'name__contains', name: t('联表数据名称'), values: [{ id: item.id, name: item.id }] });
      }
    });
    if (search.tags) {
      renderLabelRef.value.setLabel(search.tags);
      leftLabelFilterCondition.value = search.tags;
    } else {
      renderLabelRef.value.resetAllLabel();
      leftLabelFilterCondition.value = '';
    }
    listRef.value.fetchData(search);
  };

  const handleLeftWidth = (showLabel: boolean) => {
    styles.value = showLabel ? { left: '216px' } : { left: '-24px' };
  };

  // 选中左侧label 过滤表格
  const handleChecked = (name: string) => {
    searchKey.value = [];
    leftLabelFilterCondition.value = name;
    if (name) {
      searchKey.value.push({
        id: 'tags',
        name,
        values: [{
          id: name,
          name: linkDataLabelList.value.find(cItem => cItem.tag_id === name)?.tag_name || name,
        }],
      });
    }
    listRef.value.fetchData({ tags: name });
  };

  // 清空搜索
  const handleClearSearch = () => {
    const search = {
      uid: '',
      name__contains: '',
      tags: '',
      updated_by: '',
    } as Record<string, any>;
    searchKey.value = [];
    renderLabelRef.value.resetAllLabel();
    leftLabelFilterCondition.value = '';

    listRef.value.fetchData({
      ...search,
    });
  };

  const setSearchKey = () => {
    let hasKey = false;
    searchKey.value = [];
    const params = getSearchParams();
    const recordParams = getRecordPageParams();
    searchData.forEach((item) => {
      const { id, name } = item;
      if (!params[id] && (!recordParams || !recordParams[id])) return;
      const content = params[id] || recordParams[id];
      const nameList = content.split(',') as string[];

      searchKey.value.push({
        id,
        name,
        values: [{
          id: content,
          name: nameList.map(nameItem => item.children?.find(cItem => cItem.id === nameItem)?.name || nameItem).join(','),
        }],
      });
      switch (id) {
      case 'uid':
        isNeedShowDetail.value = true;
        break;
      case 'tags':
        renderLabelRef.value.setLabel(content);
        leftLabelFilterCondition.value = content;
        break;
      }
      hasKey = true;
    });
    return hasKey;
  };

  const handleRequestSuccess = (data: LinkData) => {
    fetchLinkTableTags().then(() => {
      searchData = [
        ...defaultSearchData,
        {
          name: t('标签'),
          id: 'tags',
          placeholder: t('请选择标签'),
          children: linkDataLabelList.value.map(item => ({
            name: item.tag_name,
            id: item.tag_id,
            placeholder: t('请选择标签'),
          })),
          onlyRecommendChildren: true,
        },
      ];
      setSearchKey();
    });
    total.value = data.total > total.value ? data.total : total.value;
    const { uid } = getSearchParams();
    if (uid && isNeedShowDetail.value && data.results.length) {
      detailRef.value.show(uid);
      isNeedShowDetail.value = false;
    }
  };

  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-link-data-manage-list-setting', JSON.stringify(setting));
  };

  const handleCreateUpdate = () => {
    // 编辑或者新增后重新获取version
    fetchLinkTableAll();
    handleClearSearch();
  };

  const handleShowLinkStrategy = (value: string) => {
    detailRef.value.show(value, true);
  };

  // 新增
  const handleCreate = () => {
    createRef.value.show();
  };

  // 编辑
  const handleEdit = (data: LinkDataModel) => {
    createRef.value.show(data.uid, data.strategy_count > 0);
  };

  // 详情
  const handleDetail = (data: LinkDataModel) => {
    detailRef.value.show(data.uid);
  };

  // 删除
  const handleDelete = (data: LinkDataModel) => {
    InfoBox({
      title: () => h('div', [
        h('div', t('确认删除该联表数据？')),
      ]),
      subTitle: () => h('div', {
        style: {
          fontSize: '14px',
          textAlign: 'left',
        },
      }, [
        h('div', `${t('联表数据名称')}: ${data.name}`),
        h('div', {
          style: {
            color: '#4D4F56',
            backgroundColor: '#f5f6fa',
            padding: '12px 16px',
            borderRadius: '2px',
            marginTop: '10px',
          },
        }, t('删除操作无法撤回，请谨慎操作！')),
      ]),
      confirmText: t('删除'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      class: 'link-data-delete',
      onConfirm() {
        deleteLinkData({
          uid: data.uid,
        });
      },
    });
  };

  // 查看关联策略
  const handleLinkStrategy = (data: LinkDataModel) => {
    detailRef.value.show(data.uid, true);
  };

  const fetchData = () => {
    // 获取填充地址栏参数
    const hasKey = setSearchKey();
    if (hasKey) {
      handleSearch(searchKey.value);
    } else {
      listRef.value.fetchData();
    }
  };

  onMounted(() => {
    fetchData();
  });
</script>
<style scoped lang="postcss">
.link-data-manage {
  display: flex;
  margin: -20px -24px 0;

  :deep(.edit-badge) {
    .bk-badge.pinned.top-right {
      top: 13px;
    }
  }

  .link-data-manage-list {
    position: absolute;
    right: -24px;
    padding: 24px;
    background-color: white;
    box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);

    .action-header {
      display: flex;
      margin-bottom: 20px;

      .search-input {
        width: 480px;
        margin-left: auto;
      }
    }
  }
}
</style>
<style>
.link-data-delete {
  .bk-button-primary {
    background-color: red;
    border-color: red;
  }
}
</style>

