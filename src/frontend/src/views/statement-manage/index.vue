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
    <div
      v-if="!isLoading && isEmpty"
      class="empty-wrapper">
      <bk-exception
        class="empty-content"
        :description="t('暂无数据')"
        scene="part"
        type="empty" />
    </div>
    <div
      v-else
      class="audit-router-view">
      <permission-page
        v-if="needApplyPermission"
        :data="permissionResult" />
      <router-view v-if="!needApplyPermission" />
    </div>
  </bk-loading>
</template>
<script setup lang="ts">
  import { computed, ref, watch  } from 'vue';
  import { useI18n } from 'vue-i18n';
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
  const { t } = useI18n();

  const permissionResult = ref(new ApplyDataModel());
  const needApplyPermission = ref(false);
  // 存储菜单数据用于判断是否为空
  const currentMenuData = ref<Array<{ id: string; name: string }>>([]);
  // 是否显示暂无数据
  const isEmpty = computed(() => !isLoading.value && currentMenuData.value.length === 0);

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
    run: fetchMenuListRun,
    loading: isLoading,
  } = useRequest(StatementManageService.fetchMenuList, {
    manual: true,
    defaultParams: {
      scenario: 'default',
    },
    defaultValue: [],
    onSuccess: (menuData) => {
      console.log('menuData 获取成功:', menuData);
      currentMenuData.value = menuData;
      emit('statement-menuData', menuData);
      // 菜单为空时，清空路由参数并显示空状态
      if (menuData.length === 0 && route.params?.id) {
        router.replace({ name: 'statementManage' });
      } else if (!(route.params?.id) && menuData.length > 0 && menuData[0]?.id) {
        // 仅当没有id且menuData有数据时才进行路由跳转
        router.push({
          name: 'statementManageDetail',
          params: {
            id: menuData[0].id,
          },
        });
      }
    },
  });

  // 监听子组件的刷新菜单事件
  on('refresh-menu', () => {
    console.log('收到 refresh-menu 事件，重新获取 menuData');
    fetchMenuListRun();
  });
</script>
<style lang="postcss">
  .loading {
    position: relative;
    height: 500px;
  }

  .empty-wrapper {
    position: absolute;
    top: 0;
    left: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 400px;

    .empty-content {
      font-size: 20px;
    }
  }

  .audit-router-view {
    height: 100%;
  }
</style>

