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
  <desc-popover
    ref="popoverRef"
    :width="588"
    @after-show="handleAfterShow">
    <render-field-text>
      {{ data.username || '--' }}
    </render-field-text>
    <template #content>
      <bk-loading :loading="loading || sensitiveLoading">
        <div class=" hover-table">
          <table class="hover-table-content">
            <tr
              v-for="(item, index) in colDataLeft"
              :key="index">
              <td
                class="hover-table-title"
                :style="{width: `${labelWidth}px`}">
                {{ t(item.key) }}
              </td>
              <td
                class="hover-table-value"
                :colspan="item.colspan">
                <p class="sensitive-item">
                  <multiple-line-clamp :data="(item.value as string)" />
                  <auth-button
                    v-if="sensitiveData && item.value === '******'"
                    v-bk-tooltips="t('暂无查看权限')"
                    action-id="access_audit_sensitive_info"
                    :permission="false"
                    :resource="sensitiveData.id"
                    text
                    theme="primary">
                    <audit-icon
                      class="permission-icon"
                      type="view"
                      @click="showPermissionDialog" />
                  </auth-button>
                </p>
              </td>
              <template v-if="colDataRight[index]">
                <td
                  class="hover-table-title  border-bottom"
                  :style="{width: `${labelWidth}px`}">
                  {{ t(colDataRight[index].key) }}
                </td>
                <td
                  class="hover-table-value border-bottom">
                  <p class="sensitive-item">
                    <multiple-line-clamp :data="(colDataRight[index].value as string)" />
                    <auth-button
                      v-if="sensitiveData && colDataRight[index].value === '******'"
                      action-id="access_audit_sensitive_info"
                      :permission="false"
                      :resource="sensitiveData.id"
                      style="float: right;"
                      text
                      theme="primary">
                      <audit-icon
                        v-if="colDataRight[index].value === '******'"
                        v-bk-tooltips="t('暂无查看权限')"
                        class="permission-icon"
                        type="view"
                        @click="showPermissionDialog" />
                    </auth-button>
                  </p>
                </td>
              </template>
            </tr>
          </table>
        </div>
      </bk-loading>
    </template>
  </desc-popover>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import RetrieveUserModel from '@model/meta/retrieve-user';

  import useRequest from '@hooks/use-request';

  import MultipleLineClamp from '@components/multiple-line-clamp/index.vue';

  import DescPopover from './components/desc-popover.vue';
  import RenderFieldText from './components/field-text.vue';

  interface IResult {
    key: string,
    value: string|Array<string>,
    id: string,
    type?: string,
    colspan?: number,
    subId?:string
  }
  interface Props{
    data: Record<string, any>;
  }
  const props = defineProps<Props>();
  const { t, locale } = useI18n();
  const popoverRef = ref();
  const labelWidth = computed(() => (locale.value === 'en-US' ? 120 : 84));
  const initColDataLeft = () => [
    {
      id: 'name',
      key: '姓名',
      value: '--',
    },
    {
      id: 'gender',
      key: '性别',
      value: '--',
    },
    {
      id: 'departmentText',
      key: '组织架构',
      value: '--',
      colspan: 3,
    },
  ];
  const initColDataRight = () => [
    {
      id: 'postname',
      key: '职位',
      value: '--',
    },
    {
      id: 'leaders',
      key: '直接上级',
      value: '--',
    },
  ];
  const initUserInfoDataLeft = () => [
    {
      id: 'username',
      subId: 'display_name',
      key: '用户名',
      value: '--',
    },
    {
      id: 'leader_username',
      key: '上级员工',
      value: '--',
    },
    {
      id: 'staff_status',
      key: '员工状态',
      value: '--',
    },
    {
      id: 'manager_unit_name',
      key: '签约主体',
      value: '--',
    },
    {
      id: 'department_full_name',
      key: '主岗全称',
      value: '--',
      colspan: 3,
    },
  ];
  const initUserInfoDataRight = () => [
    {
      id: 'gender',
      key: '性别',
      value: '--',
    },
    {
      id: 'dimission_date',
      key: '离职时间',
      value: '--',
    },
    {
      id: 'staff_type',
      key: '员工类型',
      value: '--',
    },
    {
      id: 'manager_level',
      key: '管理职级',
      value: '--',
    },
  ];
  const colDataLeft = ref<Array<IResult>>(initColDataLeft());
  const colDataRight = ref<Array<IResult>>(initColDataRight());

  const updateColData = (data: Array<IResult>, dataMap:RetrieveUserModel) => data.reduce((res, item) => {
    const tmpItem = { ...item };
    const value =   dataMap[item.id as keyof RetrieveUserModel];
    const subValue = dataMap[item.subId as keyof RetrieveUserModel];
    tmpItem.value = value ? `${value}${subValue ? `(${subValue})` : ''}` : tmpItem.value;
    res[res.length] = tmpItem;
    return res;
  }, [] as Array<IResult>);


  const {
    loading,
    run: fetchRetrieveUser,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(MetaManageService.fetchRetrieveUser, {
    defaultParams: {
      id: props.data.username,
    },
    defaultValue: new RetrieveUserModel(),
    onSuccess: (result) => {
      colDataLeft.value = updateColData(colDataLeft.value, result);
      colDataRight.value = updateColData(colDataRight.value, result);
    },
  });

  // 获取敏感信息列表
  const {
    data: sensitiveData,
    loading: sensitiveLoading,
    run: fetchSensitiveList,
  } = useRequest(MetaManageService.fetchSensitiveList);

  const showPermissionDialog = () => {
    popoverRef.value.hide();
  };
  const showUserInfoData = () => {
    const userInfo = props.data.snapshot_user_info;
    colDataLeft.value = updateColData(colDataLeft.value, userInfo);
    colDataRight.value = updateColData(colDataRight.value, userInfo);
    fetchSensitiveList({
      system_id: 'bk_usermgr',
      resource_type: 'sensitive_resource_object',
      resource_id: 'user',
    });
  };

  const handleAfterShow = () => {
    const userInfo = props.data.snapshot_user_info;
    if (userInfo && Object.keys(userInfo).length) {
      colDataLeft.value = initUserInfoDataLeft();
      colDataRight.value = initUserInfoDataRight();
      showUserInfoData();
    } else {
      colDataLeft.value = initColDataLeft();
      colDataRight.value = initColDataRight();
      fetchRetrieveUser({
        id: props.data.username,
      });
    }
  };
</script>
<style lang="postcss" scoped>

.sensitive-item {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .permission-icon {
    cursor: pointer;
  }
}
</style>
