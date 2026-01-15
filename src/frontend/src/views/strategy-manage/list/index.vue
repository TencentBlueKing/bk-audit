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
  <skeleton-loading
    fullscreen
    :loading="isLoading"
    name="strategyList">
    <div class="strategy-manage">
      <!-- 左侧标签-->
      <render-label
        ref="renderLabelRef"
        :labels="strategyLabelList"
        :total="total"
        :upgrade-total="upgradeTotal"
        @change="handleLeftWidth"
        @checked="handleChecked" />

      <!-- 右侧表格 -->
      <div
        class="strategy-manage-list"
        :style="styles">
        <div class="action-header">
          <auth-button
            action-id="create_strategy"
            class="w88"
            :permission="permissionCheckData"
            theme="primary"
            @click="handleCreate">
            {{ t('新建') }}
          </auth-button>
          <bk-search-select
            v-model="searchKey"
            class="search-input"
            clearable
            :condition="[]"
            :data="searchData"
            :defaut-using-item="{ inputHtml: t('请选择') }"
            :placeholder="t('策略ID、策略名称、配置方式、标签、状态')"
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
          @column-filter="handleColumnFilter"
          @on-setting-change="handleSettingChange"
          @request-success="handleRequestSuccess" />
      </div>
    </div>
  </skeleton-loading>

  <!-- 策略详情 -->
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showDetail"
    :show-footer="false"
    show-header-slot
    title="策略详情"
    :width="1100">
    <template #header>
      <div
        class="flex"
        style="width: 100%; padding-right: 40px; justify-content: space-between;">
        <div
          class="flex"
          style="align-items: center;">
          {{ t('策略详情') }}
          <bk-button
            v-bk-tooltips="t('复制链接')"
            text
            theme="primary"
            @click="handleCopyLink">
            <audit-icon
              style=" margin-left: 14px;font-size: 14px;"
              type="link" />
          </bk-button>
          <div style="height: 14px; margin: 0 10px; border-left: 1px solid #979ba5;" />
          <div style=" font-size: 14px;color: #979ba5;">
            {{ strategyItem.strategy_name }}
          </div>
        </div>
        <div style="margin-left: auto;">
          <auth-button
            v-bk-tooltips="{
              content: t('处理中，不能编辑'),
              disabled: !(strategyItem.isPending || pendingStatusIdList.includes(strategyItem.strategy_id))
            }"
            action-id="edit_strategy"
            class="w88"
            :class="{
              'is-disabled': strategyItem.isPending || pendingStatusIdList.includes(strategyItem.strategy_id)
            }"
            :permission="strategyItem.permission.edit_strategy"
            :resource="strategyItem.strategy_id"
            theme="primary"
            @click="handleEdit(strategyItem)">
            {{ t('编辑') }}
          </auth-button>
          <auth-button
            v-bk-tooltips="{
              content: t('处理中，不能克隆'),
              disabled: !(strategyItem.isPending || pendingStatusIdList.includes(strategyItem.strategy_id))
            }"
            action-id="create_strategy"
            class="ml8"
            :class="{
              'is-disabled': strategyItem.isPending || pendingStatusIdList.includes(strategyItem.strategy_id)
            }"
            :permission="permissionCheckData"
            style="width: 64px;"
            @click="handleClone(strategyItem)">
            {{ t('克隆') }}
          </auth-button>
          <bk-button
            v-if="strategyItem.isPending || pendingStatusIdList.includes(strategyItem.strategy_id)"
            v-bk-tooltips="{
              content: t('处理中，不能删除'),
            }"
            class="is-disabled ml8">
            {{ t('删除') }}
          </bk-button>
          <auth-component
            v-else
            action-id="delete_strategy"
            :permission="strategyItem.permission.delete_strategy"
            :resource="strategyItem.strategy_id">
            <bk-button
              class="ml8"
              style="width: 64px;"
              @click="handleDelete(strategyItem)">
              {{ t('删除') }}
            </bk-button>
          </auth-component>
          <span>
            <span
              class="mr8"
              style="margin-left: 24px;font-size: 14px;color: #63656e;">
              {{ t('启/停') }}
            </span>
            <auth-switch
              v-if="strategyItem.isPending
                || pendingStatusIdList.includes(strategyItem.strategy_id) || strategyItem.isFailed"
              v-bk-tooltips="{
                content: strategyItem.isFailed
                  ? t('策略状态异常，不能启停')
                  : t('处理中，不支持启停'),
              }"
              action-id="edit_strategy"
              disabled
              :model-value="strategyItem.status === 'running'"
              :permission="strategyItem.permission.edit_strategy"
              :resource="strategyItem.strategy_id"
              theme="primary" />
            <auth-component
              v-else
              action-id="edit_strategy"
              :permission="strategyItem.permission.edit_strategy"
              :resource="strategyItem.strategy_id">
              <audit-popconfirm
                class="ml8"
                :confirm-handler="() => handleChange(strategyItem)"
                :content="t(strategyItem.status === 'running'
                  ? '策略停用后对应风险可能无法及时发现，请确认是否停用'
                  : '策略启动后会开始检测并可能输出审计事件，请确认是否启动')"
                :title="t(strategyItem.status === 'running' ? '停用策略确认' : '启动策略确认')">
                <bk-switcher
                  :model-value="strategyItem.status === 'running'"
                  theme="primary" />
              </audit-popconfirm>
            </auth-component>
          </span>
        </div>
      </div>
    </template>
    <div>
      <strategy-detail
        :data="strategyItem"
        :strategy-map="strategyTagMap"
        :user-group-list="userGroupList" />
    </div>
  </audit-sideslider>

  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showRecords"
    :show-footer="false"
    :title="t('运行记录')"
    :width="960">
    <strategy-records :data="strategyItem" />
  </audit-sideslider>
  <bk-dialog
    v-model:is-show="isShowDeleteDialog"
    footer-align="center"
    :quick-close="false"
    theme="primary">
    <audit-icon
      class="alert-icon"
      svg
      type="alert" />
    <div class="strategy-delete-title">
      {{ t('确定删除该策略？') }}
    </div>
    <div
      class="strategy-delete-title-tips"
      :class="locale === 'zh-CN' ? 'strategy-delete-title-tips-zh' : ''">
      {{ t('删除的策略将') }}
      <span class="red-text">{{ t('无法找回') }}</span>
      ，{{ t('请谨慎操作') }} !
    </div>
    <div class="strategy-manage-content">
      {{ t('请输入策略名称') }}
      <span
        v-bk-tooltips="{ content: t('点击复制策略名称') }"
        class="strategy-manage-content-text"
        @click="handleCopyName">{{ deleteName }} </span>
      {{ t('以确认删除') }}
    </div>
    <bk-input
      v-model="deleteInputName"
      class="input"
      :placeholder="t('请输入待删除的策略名称')" />
    <template #footer>
      <bk-button
        class="mr8"
        :disabled="deleteInputName !== deleteName"
        theme="danger"
        @click="handleDeleteConfirm">
        {{ t('删除') }}
      </bk-button>
      <bk-button
        @click="handleClose">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script setup lang="tsx">
  import _ from 'lodash';
  import {
    computed,
    onMounted,
    ref,
    shallowRef,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';
  import {
    onBeforeRouteLeave,
    useRouter,
  } from 'vue-router';

  import ControlManageService from '@service/control-manage';
  import IamManageService from '@service/iam-manage';
  import LinkDataManageService from '@service/link-data-manage';
  import NoticeGroupManageService from '@service/notice-group';
  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import type StrategyModel from '@model/strategy/strategy';

  import useMessage from '@hooks/use-message';
  import useRecordPage from '@hooks/use-record-page';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import EditTag from '@components/edit-box/tag.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import {
    execCopy,
  } from '@utils/assist';
  import getAssetsFile from '@utils/getAssetsFile';

  import StrategyDetail from './components/detail.vue';
  import StrategyRecords from './components/records.vue';
  import RenderLabel from './components/render-label.vue';

  enum FullEnum {
    FULL = 'full',
    FUZZY = 'fuzzy'
  }
  enum SortScope {
    CURRENT = 'current',
    ALL = 'all'
  }
  const {
    getSearchParams,
    replaceSearchParams,
  } = useUrlSearch();
  const { messageSuccess, messageError } = useMessage();


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
  interface Strategy {
    page: number;
    num_pages: number;
    total: number;
    results: Array<StrategyModel>
  }
  interface Arrays {
    id: number | string,
    name: string
  }
  interface SearchData{
    name: string;
    id: string;
    children?: Array<SearchData>;
    placeholder?: string;
    multiple?: boolean;
    onlyRecommendChildren?: boolean,
  }
  interface ISettings{
    checked: Array<string>,
    fields: Record<string, any>[],
    size: string
  }
  const pendingStatusMap: Record<string, string> = {
    pending: 'pending',
    starting: 'starting',
    updating: 'updating',
    stop_failed: 'stop_failed',
    stopping: 'stopping',
  };
  let timeout: number | undefined = undefined;
  const isLoading = ref(false);
  const router = useRouter();
  const {
    recordPageParams,
    removePageParams,
    getRecordPageParams,
  } = useRecordPage;
  const isShowDeleteDialog = ref(false);
  const listRef = ref();
  const switchSuccessMap = ref<Record<string, boolean>>({});
  const showDetail = ref(false);
  const showRecords = ref(false);
  const styles = shallowRef({ left: '216px' });
  const strategyLabelList = ref<Array<{ tag_id: string, tag_name: string }>>([]);
  const searchKey = ref<Array<SearchKey>>([]);
  const strategyItem = ref({} as StrategyModel);
  const permissionCheckData = ref();
  const renderLabelRef = ref();
  const total = ref(0);
  const upgradeTotal = ref(0);
  const { locale, t } = useI18n();
  const switchStrategyParams = ref({ strategy_id: 0, toggle: false });
  const isNeedShowDetail = ref(false);
  const leftLabelFilterCondition = ref('');
  const strategyTagMap = ref<Record<string, string>>({});
  const statusMap = ref<Record<string, string>>({});
  // 挂起的需要轮询的id列表
  const pendingStatusIdList = ref<Array<number>>([]);
  // control最大版本对应的map
  const maxVersionMap = ref<Record<string, number>>({});
  const linkTableMaxVersionMap = ref<Record<string, number>>({});
  // const retryIdMap = ref<Record<number, number>>({});
  const deleteName = ref('');
  const deleteInputName = ref('');
  const deleteId = ref();
  const userGroupList = computed(() => groupList.value.results
    .reduce((result: Array<{ id: number; name: string }>, item) => {
      // eslint-disable-next-line no-param-reassign
      result[result.length] = {
        id: item.group_id,
        name: item.group_name,
      };
      return result;
    }, []));

  const validateValues = async (item: Record<string, any>, value: Array<Arrays>) => {
    if (item && item.id === 'strategy_id') {
      return /^(?:\d+,)*\d+$/.test(`${value[0].id}`) ? true : t('策略ID只允许输入整数或以,分隔的整数列表');
    }
    if (item && item.id === 'tag') {
      const tag = value[0].id;
      return strategyTagMap.value[tag] ? true : t('该标签不存在');
    }
    return true;
  };

  const defaultSearchData = [
    {
      name: t('策略ID'),
      id: 'strategy_id',
      placeholder: t('请输入策略ID (只允许输入整数)'),
    },
    {
      name: t('策略名称'),
      id: 'strategy_name',
      placeholder: t('请输入策略名称'),
    },
    {
      name: t('配置方式'),
      id: 'strategy_type',
      children: [{
        name: t('自定义规则审计'),
        id: 'rule',
        placeholder: t('请选择配置方式'),
      }, {
        name: t('引入模型审计'),
        id: 'model',
        placeholder: t('请选择配置方式'),
      }],
      placeholder: t('请选择配置方式'),
      onlyRecommendChildren: true,
    },
  ];
  let searchData: SearchData[] = [
    ...defaultSearchData,
    {
      name: t('状态'),
      id: 'status',
      multiple: true,
      placeholder: t('请选择状态'),
      onlyRecommendChildren: true,
    },
    {
      name: t('标签'),
      id: 'tag',
      placeholder: t('请选择标签'),
      onlyRecommendChildren: true,
    },

  ] as { name: string, id: string, placeholder: string, children?: any[] }[];

  const dataSource = StrategyManageService.fetchStrategyList;
  const initStatusFilterList = [
    {
      text: t('已停用', 2),
      value: 'disabled',
    },
    {
      text: t('失败'),
      value: 'failed',
    },
    {
      text: t('启动失败', 2),
      value: 'start_failed',
    },
    {
      text: t('更新失败'),
      value: 'update_failed',
    },
    {
      text: t('停用失败'),
      value: 'stop_failed',
    },
    {
      text: t('删除失败'),
      value: 'delete_failed',
    },
    {
      text: t('启动中'),
      value: 'starting',
    },
    {
      text: t('更新中'),
      value: 'updating',
    },
    {
      text: t('停用中'),
      value: 'stopping',
    },
    {
      text: t('运行中'),
      value: 'running',
    },
  ];
  const strategyTypeTextMap = {
    rule: t('自定义规则审计'),
    model: t('引入模型审计'),
  } as Record<string, string>;
  const initEnableFilterList = [
    {
      text: t('运行中'),
      value: 'running',
    },
    {
      text: t('已停用'),
      value: 'disabled',
    },
  ];
  const initTypeFilterList = [
    {
      text: t('自定义规则审计'),
      value: 'rule',
    },
    {
      text: t('引入模型审计'),
      value: 'model',
    },
  ];
  const tableColumn = ref([
    {
      label: () => t('策略ID'),
      field: () => 'strategy_id',
      fixed: 'left',
      width: 120,
      sort: 'custom',
    },
    {
      label: () => t('策略名称'),
      fixed: 'left',
      sort: 'custom',
      field: () => 'strategy_name',
      render: ({ data }: { data: StrategyModel}) => {
        const isNew = isNewData(data);
        return isNew
          ? <div style='display: flex;align-items: center;'>
          <a onClick={() => handleDetail(data)}>
            <Tooltips data={data.strategy_name} />
          </a>
          <img
              class='table-new-tip'
              src={getAssetsFile('new-tip.png')}/>
          </div>
          :  <a onClick={() => handleDetail(data)}>
            <Tooltips data={data.strategy_name} />
          </a>
        ;
      },
    },
    {
      label: () => t('配置方式'),
      filter: {
        list: initTypeFilterList,
        filterScope: SortScope.ALL,
        checked: [],
        btnSave: t('确定'),
        btnReset: t('重置'),
      },
      field: () => 'strategy_type',
      minWidth: 180,
      render: ({ data }:{data: StrategyModel}) => (
        <span style={{
          padding: '4px 6px',
          color: data.strategy_type === 'rule' ? '#299E56' : '#E38B02',
          background: data.strategy_type === 'rule' ? '#DAF6E5' : '#FDEED8',
          borderRadius: '2px',
        }}>
          { strategyTypeTextMap[data.strategy_type] }
        </span>
      ),
    },
    {
      label: () => t('标签'),
      field: () => 'tags',
      minWidth: 230,
      render: ({ data }: { data: StrategyModel }) => {
        const tags = data.tags.map(item => strategyTagMap.value[item] || item);
        return <EditTag data={tags} key={data.strategy_id} />;
      },
    },
    {
      label: () => t('状态'),
      field: () => 'status',
      width: '170px',
      filter: {
        list: initStatusFilterList,
        filterScope: SortScope.CURRENT,
        match: FullEnum.FUZZY,
        checked: [],
        btnSave: t('确定'),
        btnReset: t('重置'),
      },
      render: ({ data }: { data: StrategyModel }) => {
        if (!data.isFailed) {
          if (data.isPending) {
            return <p
              style='display: flex; align-items: center;'>
              <audit-icon
                class="rotate-loading mr4"
                svg
                type='loading' />
              <span v-bk-tooltips={{
                content: t('创建数据处理链路中，预计10分钟后策略正式运行'),
                disabled: !['pending', 'starting', 'updating'].includes(data.status),
              }}>  {statusMap.value[data.status] || data.status} </span>
              <audit-icon
                v-bk-tooltips={{
                  content: t('运行记录'),
                }}
                class='operation-records'
                style='color: #3a84ff; margin-left: 4px; cursor: pointer;'
                onClick={() => handleRecord(data)}
                type='yunxingjilu' />
            </p>;
          }
          return <p style='display: flex; align-items: center;max-width: 200px;'>
            <audit-icon
              svg
              class='mr4'
              type={data.statusTag} />
            {statusMap.value[data.status] || data.status}
            <audit-icon
              v-bk-tooltips={{
                content: t('运行记录'),
              }}
              class='operation-records'
              style='color: #3a84ff; margin-left: 4px; cursor: pointer;'
              onClick={() => handleRecord(data)}
              type='yunxingjilu' />
          </p>;
        }
        // failed
        if (data.status_msg) {
          return <p style='display: flex; align-items: baseline;'>
            <audit-icon
              class='mr4'
              svg
              type={data.statusTag} />
            <span
              style='border-bottom:1px dashed #C4C6CC;height: 32px;cursor: pointer;'
              v-bk-tooltips={data.status_msg}>
              {statusMap.value[data.status] || data.status}
            </span>
            <p>
              <span>, </span>
              <bk-button
                text
                theme='primary'
                onClick={() => retryRequest(data.strategy_id)}>
                {t('重试')}
              </bk-button>
            </p>
            <p class='err-underline' />
            <audit-icon
              v-bk-tooltips={{
                content: t('运行记录'),
              }}
              class='operation-records'
              style='color: #3a84ff; margin-left: 4px; cursor: pointer;'
              onClick={() => handleRecord(data)}
              type='yunxingjilu' />
          </p>;
        }
        return <div style='display: flex; align-items: center;'>
          <audit-icon
            svg
            class='mr4'
            type={data.statusTag} />
          <span>{statusMap.value[data.status] || data.status}</span>
          <p>
            <span>, </span>
            <bk-button
              text
              theme='primary'
              onClick={() => retryRequest(data.strategy_id)}>
              {t('重试')}
            </bk-button>
          </p>
          <audit-icon
            v-bk-tooltips={{
              content: t('运行记录'),
            }}
            class='operation-records'
            style='color: #3a84ff; margin-left: 4px; cursor: pointer;'
            onClick={() => handleRecord(data)}
            type='yunxingjilu' />
        </div>;
      },
    },
    {
      label: () => t('产生风险单'),
      field: () => 'risk_count',
      sort: 'custom',
      render: ({ data }: { data: StrategyModel }) => {
        const to = {
          name: 'riskManageList',
          query: {
            strategy_id: data.strategy_id,
          },
        };
        return data.risk_count ? <router-link to = {to} target='_blank'>
          <span v-bk-tooltips={{
            content: t('近6个月此策略产生风险单总数，点击查看'),
            disabled: !data.risk_count,
          }}>{data.risk_count}</span>
        </router-link> : <span>{data.risk_count}</span>;
      },
    },
    {
      label: () => t('启停'),
      field: () => 'status',
      width: 110,
      filter: {
        list: initEnableFilterList,
        filterScope: SortScope.ALL,
        // match: FullEnum.FULL,
        checked: [],
        btnSave: t('确定'),
        btnReset: t('重置'),
      },
      render: ({ data }: { data: StrategyModel }) => {
        if (data.isPending || data.isFailed) {
          return <auth-switch
          action-id="edit_strategy"
          permission={data.permission.edit_strategy}
          size="small"
          resource={data.strategy_id}
          theme="primary"
          v-bk-tooltips={{
            content: data.isFailed
              ? t('策略状态异常，不能启停')
              : t('处理中，不支持启停'),
          }}
          disabled
        />;
        }
        return <audit-popconfirm
        title={t(data.status === 'running' ? '停用策略确认' : '启动策略确认')}
        content={t(data.status === 'running' ? '策略停用后对应风险可能无法及时发现，请确认是否停用' : '策略启动后会开始检测并可能输出审计事件，请确认是否启动')}
        confirmHandler={() => handleChange(data)}>
        <auth-switch
          action-id="edit_strategy"
          permission={data.permission.edit_strategy}
          size="small"
          model-value={data.status === 'running'}
          resource={data.strategy_id}
          theme="primary"
        />
      </audit-popconfirm>;
      },
    },
    {
      label: () => t('最近更新人'),
      field: () => 'updated_by',
      width: 140,
      sort: 'custom',
    },
    {
      label: () => t('最近更新时间'),
      field: () => 'updated_at',
      sort: 'custom',
      width: 170,
    },
    {
      label: () => t('创建人'),
      field: () => 'created_by',
      width: 140,
    },
    {
      label: () => t('创建时间'),
      field: () => 'created_at',
      width: 170,
    },
    {
      fixed: 'right',
      label: () => t('操作'),
      width: '120px',
      render: ({ data }: { data: StrategyModel }) => <>
      {
        data.isPending
          ? <bk-button
            text
            class="is-disabled"
            v-bk-tooltips={t('处理中，不能编辑')}>
            {t('编辑')}
          </bk-button>
          : <bk-badge
            class='edit-badge'
            position="top-right"
            theme="danger"
            visible={ data.strategy_type === 'rule'
              ? (data.link_table_version || 999) >= (linkTableMaxVersionMap.value[data.link_table_uid] || 1)
              : data.control_version >= (maxVersionMap.value[data.control_id] || 1)
            }
            dot
          >
            <auth-button
              actionId="edit_strategy"
              permission={data.permission.edit_strategy}
              resource={data.strategy_id}
              v-bk-tooltips={{
                content: data.strategy_type === 'rule' ? t('策略使用的联表，有新版本待升级') : t('策略使用的方案，有新版本待升级'),
                disabled: data.strategy_type === 'rule'
                  ? (data.link_table_version || 999) >= (linkTableMaxVersionMap.value[data.link_table_uid] || 1)
                  : data.control_version >= (maxVersionMap.value[data.control_id] || 1),
              }}
              theme="primary"
              text
              onClick={() => handleEdit(data)}>
              {t('编辑')} {data.link_table_version >= (linkTableMaxVersionMap.value[data.link_table_uid] || 1)}
            </auth-button>
          </bk-badge>
      }
      {
        data.isPending
          ? <bk-button
            text
            class="is-disabled ml8"
            v-bk-tooltips={t('处理中，不能克隆')}>
            {t('克隆')}
          </bk-button>
          : <auth-button
            actionId="create_strategy"
            permission={permissionCheckData.value}
            class="ml8"
            theme="primary"
            onClick={() => handleClone(data)}
            text>
            {t('克隆')}
          </auth-button>
      }

      <bk-dropdown
        popover-options={{
          extCls: showRecords.value ? 'strategy-operation-dropdown-pop' : '',
        }}
        trigger="click"
        style="margin-left: 8px">
        {{
          default: () => <bk-button text>
            <audit-icon type="more" />
          </bk-button>,
          content: () => (
            <bk-dropdown-menu>
              <bk-dropdown-item>
                <bk-button
                  text
                  class="ml8"
                  onClick={() => handleRecord(data)}
                  v-bk-tooltips={t('运行记录')}>
                  {t('运行记录')}
                </bk-button>
              </bk-dropdown-item>
              <bk-dropdown-item>
                {data.isPending ? (
                  <bk-button
                    text
                    class="is-disabled ml8"
                    v-bk-tooltips={t('处理中，不能删除')}>
                    {t('删除')}
                  </bk-button>
                ) : (
                    <auth-button
                      style="width: 100%;"
                      actionId="delete_strategy"
                      permission={data.permission.delete_strategy}
                      resource={data.strategy_id}
                      onClick={() => handleDelete(data)}
                      text>
                      {t('删除')}
                    </auth-button>
                )}
              </bk-dropdown-item>
            </bk-dropdown-menu>
          ),
        }}
      </bk-dropdown>
    </>,
    },
  ] as any[]);

  const handleDelete = (data: StrategyModel) => {
    isShowDeleteDialog.value = true;
    deleteName.value = data.strategy_name;
    deleteId.value = Number(data.strategy_id);
  };
  const handleCopyName = () => {
    execCopy(deleteName.value, t('复制成功'));
  };
  const handleDeleteConfirm = () => {
    handleRemove(deleteId.value);
    isShowDeleteDialog.value = false;
    deleteName.value = '';
    deleteInputName.value = '';
  };
  const handleClose = () => {
    isShowDeleteDialog.value = false;
    deleteName.value = '';
    deleteInputName.value = '';
    deleteId.value = null;
  };
  const disabledMap: Record<string, string> = {
    strategy_id: 'strategy_id',
    strategy_name: 'strategy_name',
    risk_count: 'risk_count',
    tags: 'tags',
    status: 'status',
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
    checked: ['strategy_id', 'strategy_name', 'risk_count', 'tags', 'status', 'updated_by', 'updated_at'],
    showLineHeight: false,
  });
  const settings = computed(() => {
    const jsonStr = localStorage.getItem('audit-strategy-manage-list-setting');
    if (jsonStr) {
      const jsonSetting = JSON.parse(jsonStr);
      jsonSetting.showLineHeight = false;
      return jsonSetting;
    }
    return initSettings();
  });


  const {
    run: fetchGroupList,
    data: groupList,
  } = useRequest(NoticeGroupManageService.fetchGroupList, {
    defaultValue: {
      page: 1,
      num_pages: 1,
      results: [],
      total: 0,
    },
  });

  const {
    run: retryStrategy,
  } = useRequest(StrategyManageService.retryStrategy, {
    defaultValue: null,
    onSuccess() {
      fetchData();
    },
  });


  // 获取策略新建权限
  useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'create_strategy',
    },
    defaultValue: {},
    manual: true,
    onSuccess: (data) => {
      permissionCheckData.value = data.create_strategy;
    },
  });
  // 获取标签列表
  const {
    run: fetchStrategyTags,
    data: labelList,
  } = useRequest(StrategyManageService.fetchStrategyTags, {
    defaultParams: {
      page: 1,
      page_size: 1,
    },
    defaultValue: [],
    // manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
      });
      strategyLabelList.value = data;
    },
  });
  // 获取版本信息
  useRequest(ControlManageService.fetchControlTypes, {
    defaultValue: [],
    defaultParams: {
      control_type_id: 'AIOps',
    },
    manual: true,
    onSuccess(data) {
      maxVersionMap.value = data.reduce((res, item) => {
        res[item.control_id] = item.versions[0].control_version;
        return res;
      }, {} as Record<string, number>);
    },
  });
  // 获取全部联表版本信息
  useRequest(LinkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      linkTableMaxVersionMap.value = data.reduce((res, item) => {
        res[item.uid] = item.version;
        return res;
      }, {} as Record<string, number>);
    },
  });
  const {
    run: fetchStrategyCommon,
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    onSuccess(data) {
      statusMap.value = data.strategy_status.reduce((res: Record<string, string>, item: {
        label: string;
        value: string
      }) => {
        res[item.value] = item.label;
        return res;
      }, {});
    },
  });

  // 启停
  const {
    run: fetchSwitchStrategy,
  } = useRequest(StrategyManageService.fetchSwitchStrategy, {
    defaultValue: {},
    onSuccess() {
      const { toggle, strategy_id: id } = switchStrategyParams.value;
      messageSuccess(toggle ? t('策略启用中，预计最长10分钟后开始正式运行') : t('策略停用中，预计最长2分钟后停用成功'));
      fetchData();
      switchSuccessMap.value[id] = true;
      strategyItem.value.status = toggle ? 'running' : 'disabled';
    },
  });

  // 删除
  const {
    run: remove,
  } = useRequest(StrategyManageService.remove, {
    defaultValue: {},
    onSuccess: () => {
      showDetail.value = false;
      listRef.value.refreshList();
      messageSuccess(t('删除成功'));
    },
  });
  // 获取状态
  const {
    run: fetchStrategyStatus,
  } = useRequest(StrategyManageService.fetchStrategyStatus, {
    defaultValue: {},
    onSuccess: (data) => {
      pendingStatusIdList.value = [];
      const listData = listRef.value.getListData();
      Object.keys(data).forEach((id) => {
        if (pendingStatusMap[data[id].status]) {
          pendingStatusIdList.value.push(Number(id));
        }
        const item = listData.find((item: StrategyModel) => `${item.strategy_id}` === `${id}`);
        if (item) {
          item.status = data[id].status;
          item.status_msg = data[id].status_msg;
        }
      });
      timeout = undefined;
      startPollingStatus();
    },
  });

  // 发起重试请求
  const retryRequest = (strategyId: number) => {
    recordPageParams();
    // retryIdMap.value[strategyId] = strategyId;
    retryStrategy({
      strategy_id: strategyId,
    });
  };
  // 搜索
  const handleSearch = (keyword: Array<any>) => {
    const search = {
      strategy_id: undefined,
      strategy_name: '',
      strategy_type: '',
      tag: '',
      status: '',
    } as Record<string, any>;

    keyword.forEach((item: SearchKey, index) => {
      if (item.values) {
        const value = item.values.map(item => item.id).join(',');
        search[item.id] = value;
      } else {
        // 默认输入字段后匹配套餐名字
        const list = search.strategy_name.split(',').filter((item: string) => !!item);
        list.push(item.id);
        _.uniq(list);
        search.strategy_name = list.join(',');
        searchKey.value[index] = ({ id: 'strategy_name', name: t('策略名称'), values: [{ id: item.id, name: item.id }] });
      }
    });
    // 对列表的filter重新赋值
    tableColumn.value.forEach((column) => {
      if (column.filter && Array.isArray(column.filter.checked)) {
        // eslint-disable-next-line no-param-reassign
        column.filter.checked.length = 0;
      }
    });

    if (search.tag) {
      renderLabelRef.value.setLabel(search.tag);
      leftLabelFilterCondition.value = search.tag;
    } else {
      renderLabelRef.value.resetAllLabel();
      leftLabelFilterCondition.value = '';
    }
    listRef.value.fetchData(search);
  };

  const handleSettingChange = (setting: ISettings) => {
    localStorage.setItem('audit-strategy-manage-list-setting', JSON.stringify(setting));
  };
  // 将新建的tr高亮
  const setNewCreateTrHighlight = (index: number, isNew : boolean) => {
    const domList = document.querySelectorAll(`.audit-highlight-table .bk-table-body tbody tr:nth-child(${index + 1}) td`);
    if (domList) {
      domList.forEach((dom) => {
        const el = dom as HTMLElement;
        el.style.background = isNew ? '#f2fff4' : '#fff';
      });
    }
  };
  // 判断是否是新建数据
  const isNewData = (data: StrategyModel) => {
    const time = new Date(data.created_at).getTime();
    const now = new Date().getTime();
    const diff = Math.abs(now - time);
    const isNew = diff < (5 * 60 * 1000);
    return isNew;
  };
  // 复制分享链接
  const handleCopyLink = () => {
    replaceSearchParams({ strategy_id: strategyItem.value.strategy_id });
    const route = window.location.href;
    execCopy(route, t('复制成功'));
  };

  // 详情
  const handleDetail = (data: StrategyModel) => {
    if (!data) return;
    strategyItem.value = data;
    showDetail.value = true;
  };

  // 运行记录
  const handleRecord = (data: StrategyModel) => {
    strategyItem.value = data;
    showRecords.value = true;
  };

  // 新建
  const handleCreate = () => {
    removePageParams();
    router.push({
      name: 'strategyCreate',
    });
  };

  // 编辑
  const handleEdit = (data: StrategyModel) => {
    if (data.isPending) return;
    recordPageParams();
    router.push({
      name: 'strategyEdit',
      params: {
        id: data.strategy_id,
      },
    });
  };

  // 克隆
  const handleClone = (data: StrategyModel) => {
    if (data.isPending || pendingStatusIdList.value.includes(data.strategy_id)) return;
    recordPageParams();
    router.push({
      name: 'strategyClone',
      params: {
        id: data.strategy_id,
      },
    });
  };

  const handleLeftWidth = (showLabel: boolean) => {
    styles.value = showLabel ? { left: '216px' } : { left: '-24px' };
  };


  // 筛选过滤
  const handleColumnFilter = (checkedObj: Record<string, any>) => {
    const checkField = checkedObj.column.field();
    // const { index } = checkedObj;
    const value = checkedObj.checked.join(',');
    // tableColumn.value.forEach((column, colIndex) => {
    //   if (column.filter && Array.isArray(column.filter.checked) && index !== colIndex) {
    //     // eslint-disable-next-line no-param-reassign
    //     column.filter.checked.length = 0;
    //   }
    // });
    listRef.value.fetchData({
      [checkField]: value,
    });
    const findObj = searchKey.value.find(item => item.id === checkField);
    const nameList = value.split(',') as string[];
    if (value && checkField === 'status') {
      if (findObj) {
        findObj.values = [{
          id: value,
          name:
            nameList.map(nameItem => initStatusFilterList?.find(cItem => cItem.value === nameItem)?.text || nameItem).join(','),
        }];
      } else {
        searchKey.value.push({
          id: 'status',
          name: t('状态'),
          values: [{
            id: value,
            name:
              nameList.map(nameItem => initStatusFilterList?.find(cItem => cItem.value === nameItem)?.text || nameItem).join(','),
          }],
        });
      }
    } else {
      searchKey.value = [];
    }
  };
  // 清空搜索
  const handleClearSearch = () => {
    const search = {
      strategy_id: undefined,
      strategy_name: '',
      strategy_type: '',
      tag: '',
      status: '',
    } as Record<string, any>;
    searchKey.value = [];
    renderLabelRef.value.resetAllLabel();
    leftLabelFilterCondition.value = '';

    tableColumn.value.forEach((column) => {
      if (column.filter && Array.isArray(column.filter.checked)) {
        // eslint-disable-next-line no-param-reassign
        column.filter.checked.length = 0;
      }
    });

    listRef.value.fetchData({
      ...search,
    });
  };
  // 启停
  const handleChange = (data: StrategyModel) => {
    const { status } = data;
    switchSuccessMap.value[data.strategy_id] = false;
    switchStrategyParams.value = {
      strategy_id: data.strategy_id,
      toggle: status !== 'running',
    };
    recordPageParams();
    return fetchSwitchStrategy(switchStrategyParams.value)
      .then(() => {
        if (switchSuccessMap.value[data.strategy_id]) return;
        messageError(status !== 'running' ? t('策略启用失败') : t('策略停用失败'));
      });
  };
  // 删除
  const handleRemove = (id: number) => remove({
    id,
  });
  // 选中左侧label 过滤表格
  const handleChecked = (name: string) => {
    searchKey.value = [];
    leftLabelFilterCondition.value = name;
    if (name) {
      searchKey.value.push({
        id: 'tag',
        name,
        values: [{
          id: name,
          name: strategyLabelList.value.find(cItem => cItem.tag_id === name)?.tag_name || name,
        }],
      });
    }
    listRef.value.fetchData({ tag: name });
  };
  let isRequest = false;
  const handleRequestSuccess = (data: Strategy) => {
    // 先检验策略列表权限再获取通知组
    if (!groupList.value.results.length) {
      fetchGroupList();
    }
    if (!isRequest) {
      Promise.all([fetchStrategyTags(), fetchStrategyCommon()]).then(() => {
        searchData = [
          ...defaultSearchData,
          {
            name: t('状态'),
            id: 'status',
            placeholder: t('请选择状态'),
            multiple: true,
            children: commonData.value.strategy_status.map((item: { label: string; value: string }) => ({
              name: item.label,
              id: item.value,
              placeholder: t('请选择状态'),
            })),
            onlyRecommendChildren: true,
          },
          {
            name: t('标签'),
            id: 'tag',
            placeholder: t('请选择标签'),
            children: strategyLabelList.value.map(item => ({
              name: item.tag_name,
              id: item.tag_id,
              placeholder: t('请选择标签'),
            })),
            onlyRecommendChildren: true,
          },
        ];
        setSearchKey();
      });
      isRequest = true;
    }

    pendingStatusIdList.value = data.results
      .filter(item => item.isPending)
      .map(item => item.strategy_id);

    // 如果有pending状态就开始轮询
    startPollingStatus();

    total.value = data.total > total.value ? data.total : total.value;

    const { strategy_id: strategyId } = getSearchParams();
    if (strategyId && strategyId.split(',').length === 1  && isNeedShowDetail.value) {
      handleDetail(data.results[0]);
      isNeedShowDetail.value = false;
      strategyLabelList.value = [];
    } else if (!strategyLabelList.value.length) {
      strategyLabelList.value = labelList.value;
    }

    setTimeout(() => {
      data.results.forEach((item, index) => {
        const isNew = isNewData(item);
        setNewCreateTrHighlight(index, isNew);
      });
    }, 1000);
  };

  const startPollingStatus = () => {
    clearTimeout(timeout);
    if (pendingStatusIdList.value.length) {
      timeout = setTimeout(() => {
        fetchStrategyStatus({
          strategy_ids: pendingStatusIdList.value.join(','),
        });
      }, 5000);
    }
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
      case 'strategy_id':
        isNeedShowDetail.value = true;
        break;
      case 'tag':
        renderLabelRef.value.setLabel(content);
        leftLabelFilterCondition.value = content;
        break;
      }
      hasKey = true;
    });
    return hasKey;
  };
  const fetchData = () => {
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
  onBeforeRouteLeave(() => {
    clearTimeout(timeout);
  });
</script>
<style lang="postcss">
.table-new-tip {
  height: 14px;

  /* position: absolute; */

  /* right: 0; */
  margin-left: 8px;
}

.mr4 {
  margin-right: 4px;
}

.bk-popper {
  max-width: 1000px;
}

.strategy-manage {
  display: flex;
  margin: -20px -24px 0;

  .edit-badge {
    .bk-badge.pinned.top-right {
      top: 13px;
    }
  }

  .strategy-enable-switch {
    margin-left: 5px;
  }

  .strategy-manage-list {
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

    .label-box {
      display: inline-block;
      height: 23px;
      padding: 0 10px;
      margin-right: 4px;
      line-height: 22px;
      text-align: center;
      background-color: #f0f1f5;
      border-radius: 2px;
    }

    .notice-box .bk-tag {
      height: 23px;
      max-width: 220px;
      padding: 0 10px;
      margin-right: 4px;
      overflow: hidden;
      line-height: 22px;
      text-align: center;
      text-overflow: ellipsis;
      white-space: nowrap;
      background: #fafbfd;
      border: 1px solid rgb(151 155 165 / 30%);
      border-radius: 2px;
    }
  }
}

.operation-records {
  display: none;
}

.hover-highlight {
  &:hover {
    .operation-records {
      display: inline-block;
    }
  }
}

.strategy-operation-dropdown-pop {
  z-index: 2000 !important;
}

.alert-icon {
  position: absolute;
  top: 0;
  left: 50%;
  font-size: 42px;
  transform: translate(-50%, -50%)
}

.strategy-delete-title {
  margin-top: 20px;
  font-size: 20px;
  line-height: 32px;
  letter-spacing: 0;
  color: #313238;
  text-align: center;
}

.strategy-delete-title-tips {
  width: 416px;
  height: 46px;
  margin: 0 auto;
  margin-top: 20px;
  margin-bottom: 20px;
  font-size: 12px;
  color: #63656e;
  text-align: center;
  overflow-wrap: break-word;
  background: #f5f6fa;
  border-radius: 2px;

  .red-text {
    color: #ea3636;
  }
}

.strategy-delete-title-tips-zh {
  line-height: 46px;

}

.strategy-manage-content {
  width: 416px;
  padding-bottom: 10px;
  font-size: 14px;
  color: #333;
  text-align: center;

  .strategy-manage-content-text {
    font-weight: 700;
    cursor: pointer;
  }
}
</style>
