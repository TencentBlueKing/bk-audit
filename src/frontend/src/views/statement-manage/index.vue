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
  <bk-loading
    class="loading"
    :loading="isLoading">
    <div class="audit-router-view">
      <permission-page
        v-if="needApplyPermission"
        :data="permissionResult" />
      <router-view v-if="!needApplyPermission" />
    </div>
  </bk-loading>
</template>
<script setup lang="ts">
  import { ref, watch  } from 'vue';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import StatementManageService from '@service/statement-manage';

  import ApplyDataModel from '@model/iam/apply-data';

  import useEventBus from '@hooks/use-event-bus';
  import useRequest from '@hooks/use-request';

  import PermissionPage from '@components/apply-permission/page.vue';

  const { on } = useEventBus();

  const permissionResult = ref(new ApplyDataModel());
  const needApplyPermission = ref(false);

  const { emit } = useEventBus();
  const router = useRouter();
  const route = useRoute();

  // 每次切换菜单时重新设置无权限为false，防止出现一个菜单没有权限后，切换其他正常菜单，仍然是无权限页面
  watch(() => route, () => {
    if (route.params.id !== '' && route.name === 'statementManageDetail') {
      needApplyPermission.value = false;
    }
  }, {
    deep: true,
  });

  on('permission-page', (data) => {
    needApplyPermission.value = true;
    permissionResult.value = data as ApplyDataModel;
  });

  // 获取审计报表左侧菜单
  const {
    loading: isLoading,
  } = useRequest(StatementManageService.fetchMenuList, {
    manual: true,
    defaultParams: {
      scenario: 'default',
    },
    defaultValue: [],
    onSuccess: (menuData) => {
      emit('statement-menuData', menuData);
      // 仅当没有id且menuData有数据时才进行路由跳转
      if (!(route.params?.id) && menuData.length > 0 && menuData[0]?.id) {
        router.push({
          name: 'statementManageDetail',
          params: {
            id: menuData[0].id,
          } });
      }
    },
  });
</script>
<style lang="postcss">
  .loading {
    height: 500px;
  }
</style>

