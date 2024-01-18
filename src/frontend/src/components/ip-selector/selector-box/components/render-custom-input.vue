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
  <div class="render-custom-input">
    <div class="left-input">
      <bk-input
        v-model="ipInput"
        :placeholder="t('输入主机IP')"
        :rows="25"
        type="textarea"
        @input="handleIPInput" />
      <div
        v-if="inputError"
        class="input-error">
        {{ inputError }}
      </div>
      <div
        class="input-btn"
        @click="handleParseIP">
        {{ t('点击解析') }}
      </div>
    </div>
    <div class="right-host-list">
      <bk-input
        v-model="searchKey"
        :placeholder="t('搜索IP/主机名')" />
      <div class="host-type-box">
        <div
          class="item"
          :class="{active: hostListType === 'intranet'}"
          @click="handleHostListTypeChanage('intranet')">
          {{ t('内网IP') }}（{{ hostIntranetNum }}）
        </div>
        <div
          class="item"
          :class="{ active: hostListType === 'extranet'}"
          @click="handleHostListTypeChanage('extranet')">
          {{ t('外网IP') }}（{{ hostExtranetNum }}）
        </div>
      </div>
      <bk-loading :loading="isParseLoading">
        <table>
          <thead>
            <tr>
              <th style="width: 20px;">
                <list-check
                  :disabled="hostInstanceList.length < 1"
                  :value="listCheckValue"
                  @change="handleListCheckChange" />
              </th>
              <th style="width: 120px;">
                IP
              </th>
              <th style="white-space: nowrap;">
                {{ t('Agent 状态') }}
              </th>
              <th style="white-space: nowrap;">
                {{ t('云区域') }}
              </th>
              <th style="width: 80px;white-space: nowrap;">
                {{ t('操作系统') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="hostBaseInfo in renderList"
              :key="getHostKey(hostBaseInfo)"
              @click="handleTableRowClick(hostBaseInfo)">
              <td>
                <bk-checkbox
                  label
                  :model-value="Boolean(checkedMap[getHostKey(hostBaseInfo)])" />
              </td>
              <td>
                <div class="cell-text">
                  {{ hostBaseInfo.ip }}
                </div>
              </td>
              <td>
                <div class="cell-text">
                  {{ hostBaseInfo.agent_status_name }}
                </div>
              </td>
              <td>
                <div class="cell-text">
                  {{ hostBaseInfo.bk_cloud_name }}
                </div>
              </td>
              <td style="width: 80px;">
                <div class="cell-text">
                  {{ hostBaseInfo.bk_os_type || '--' }}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <bk-exception
          v-if="renderList.length < 1"
          class="exception-part"
          scene="part"
          type="search-empty">
          {{ t('暂无数据') }}
        </bk-exception>
        <bk-pagination
          v-if="showPagination"
          v-model="pagination.modelValue"
          align="center"
          class="mt8"
          :count="pagination.count"
          :limit="pagination.limit"
          :show-limit="false"
          :show-total-count="false"
          small />
      </bk-loading>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
    shallowRef,
    triggerRef,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BizManageService from '@service/biz-manage';

  import type HostInstanceStatusModel from '@model/biz/host-instance-status';

  import useRequest from '@hooks/use-request';

  import { IPRule } from '@utils/validator';

  import useListCheck from '../hooks/use-list-check';
  import useRenderList from '../hooks/use-render-list';

  import ListCheck from './list-check.vue';
  import { getHostKey } from './utils';

  interface Props {
    bizId: number
  }
  interface Emits {
    (e: 'change', type: 'staticTopo', value: Array<HostInstanceStatusModel>): void
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  type THostCheckedMap = { [key: string]: HostInstanceStatusModel }

  const { t } = useI18n();

  const ipInput = ref('');
  const inputError = ref('');
  const hostListType = ref('intranet');
  const hostIntranetNum = ref(0);
  const hostExtranetNum = ref(0);
  const checkedMap = shallowRef<THostCheckedMap>({});

  // 获取 IP 的主机信息
  const {
    loading: isParseLoading,
    data: hostInstanceList,
    run: fetchHostBaseInfo,
  } = useRequest(BizManageService.fetchHostBaseInfo, {
    defaultValue: [],
    onSuccess(data) {
      hostIntranetNum.value = data.filter(item => item.is_innerip).length;
      hostExtranetNum.value = data.length - hostIntranetNum.value;
    },
  });

  // 本地分页
  const {
    showPagination,
    searchKey,
    pagination,
    renderList,
  } = useRenderList(
    hostInstanceList,
    (hostInfo, rule) => rule.test(hostInfo.ip)
      && hostInfo.is_innerip === (hostListType.value === 'intranet'),
  );
  const listCheckValue = useListCheck(hostInstanceList, renderList, checkedMap, 'primaryKey');

  const triggerChange = () => {
    triggerRef(checkedMap);
    emits('change', 'staticTopo', Object.values(checkedMap.value));
  };

  const handleIPInput = () => {
    inputError.value = '';
  };
  const handleParseIP = () => {
    const stack = ipInput.value.split(/[;\n, ]/);
    for (let i = 0 ; i < stack.length ; i++) {
      if (!IPRule.validator(stack[i])) {
        inputError.value = t('IP格式有误或不存在，检查后重试！');
        return;
      }
    }
    fetchHostBaseInfo({
      biz_id: props.bizId,
      ip_list: stack.map(ip => ({ ip })),
    });
  };

  const handleHostListTypeChanage = (listType: string) => {
    hostListType.value = listType;
  };
  // 本页全选、跨页全选
  const handleListCheckChange = (type: string) => {
    if (type === 'page') {
      renderList.value.forEach((item) => {
        checkedMap.value[item.primaryKey] = item;
      });
    } else if (type === 'pageCancel') {
      renderList.value.forEach((item) => {
        delete checkedMap.value[item.primaryKey];
      });
    } else if (type === 'all') {
      hostInstanceList.value.forEach((item) => {
        checkedMap.value[item.primaryKey] = item;
      });
    } else if (type === 'allCancel') {
      checkedMap.value = {};
    }
    triggerChange();
  };
  // 选中主机
  const handleTableRowClick = (hostBaseInfo: HostInstanceStatusModel) => {
    const hostKey = hostBaseInfo.primaryKey;
    if (checkedMap.value[hostKey]) {
      delete checkedMap.value[hostKey];
    } else {
      checkedMap.value[hostKey] = hostBaseInfo;
    }
    triggerChange();
  };
</script>
<style lang="postcss">
  .render-custom-input {
    display: flex;

    .bk-checkbox {
      margin-right: 0;
    }

    .left-input {
      flex: 0 0 240px;
      height: 460px;

      .input-error {
        position: absolute;
        width: 100%;
        margin-top: 2px;
        font-size: 12px;
        line-height: 20px;
        color: #ea3636;
        text-align: left;
      }

      .input-btn {
        width: 240px;
        height: 32px;
        margin-top: 24px;
        font-size: 12px;
        line-height: 32px;
        color: #3a84ff;
        text-align: center;
        cursor: pointer;
        background: #fff;
        border: 1px solid #3a84ff;
        border-radius: 2px;
        transition: all .15s;

        &:hover {
          color: #fff;
          background: #3a84ff;
        }
      }
    }

    .right-host-list {
      padding-left: 20px;
      overflow: hidden;
      flex: 0 0 480px;

      table {
        width: 100%;
        margin-top: 12px;
        font-size: 12px;
        text-align: left;

        tr {
          border-bottom: 1px solid #e7e8ed;
        }

        th {
          height: 40px;
          font-weight: normal;
          line-height: 40px;
          vertical-align: middle;
          background: #f5f6fa;
        }

        th,
        td {
          height: 40px;
          padding: 0 8px;
        }

        .cell-text {
          display: block;
          height: 20px;
          overflow: hidden;
          text-align: left;
          text-overflow: ellipsis;
          word-break: break-all;
          white-space: normal;
          direction: rtl;
        }
      }
    }

    .host-type-box {
      display: flex;
      margin-top: 3px;
      font-size: 12px;
      line-height: 36px;
      color: #63656e;
      border-bottom: 1px solid #dcdee5;
      user-select: none;

      .item {
        position: relative;

        &.active {
          color: #3a84ff;

          &::after {
            position: absolute;
            right: 0;
            bottom: -1px;
            left: 0;
            height: 2px;
            background: #3a84ff;
            content: '';
          }
        }

        &:nth-child(n+2) {
          margin-left: 24px;
        }

        cursor: pointer;
      }
    }
  }
</style>
