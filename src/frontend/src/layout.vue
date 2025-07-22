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
  <audit-navigation @menu-flod="handleSideMenuFlodChange">
    <template #logo>
      <img
        :src="platformConfig.appLogo"
        style="width: 28px; margin-left: 16px;cursor: pointer;"
        @click="handleRouterChange('handleManage')">
      <span
        class="site-title"
        @click="handleRouterChange('handleManage')">
        {{ platformConfig.i18n.productName }}
      </span>
    </template>
    <template #header>
      <slot name="header" />
    </template>
    <template #headerCenter>
      <div class="main-navigation-left">
        <router-link
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'auditRiskManage'
          }"
          :to="{ name:'handleManage', query: {} }">
          {{ t('审计风险') }}
        </router-link>
        <router-link
          v-if="hasBkvision.enabled"
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'auditStatement'
          }"
          :to="{ name:'statementManage', query: {} }">
          {{ t('审计报表') }}
        </router-link>
        <router-link
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'auditConfigurationManage'
          }"
          :to="{ name:'analysisManage', query: {} }">
          {{ t('审计配置') }}
        </router-link>
      </div>
    </template>
    <template #headerRight>
      <slot name="headerRight" />
    </template>
    <template #side>
      <audit-menu
        :floded="isMenuFlod"
        @change="handleRouterChange">
        <template v-if="curNavName === 'auditConfigurationManage'">
          <audit-menu-item-group>
            <template #title>
              <div> {{ t('分析') }}</div>
            </template>
            <template #flod-title>
              <div>{{ t('分析') }}</div>
            </template>
            <audit-menu-item index="analysisManage">
              <audit-icon
                class="menu-item-icon"
                type="search" />
              {{ t('检索') }}
            </audit-menu-item>
          </audit-menu-item-group>
          <audit-menu-item-group>
            <template #title>
              <div>{{ t('跟踪') }}</div>
            </template>
            <template #flod-title>
              <div>{{ t('跟踪') }}</div>
            </template>
            <audit-menu-item index="strategyManage">
              <audit-icon
                class="menu-item-icon"
                type="celve" />
              {{ t('审计策略') }}
            </audit-menu-item>
            <!-- <audit-menu-item index="eventManage">
              <audit-icon
                class="menu-item-icon"
                type="gaojingshijian" />
              {{ t('审计风险') }}
            </audit-menu-item> -->
            <audit-menu-item index="linkDataManage">
              <audit-icon
                class="menu-item-icon"
                type="lianbiao" />
              {{ t('联表管理') }}
            </audit-menu-item>
            <audit-menu-item index="noticeGroup">
              <audit-icon
                class="menu-item-icon"
                type="tongzhizu" />
              {{ t('通知组') }}
            </audit-menu-item>
          </audit-menu-item-group>

          <audit-menu-item-group>
            <template #title>
              <div>{{ t('风险') }}</div>
            </template>
            <template #flod-title>
              <div>{{ t('风险') }}</div>
            </template>
            <audit-menu-item index="ruleManage">
              <audit-icon
                class="menu-item-icon"
                type="insert" />
              {{ t('处理规则') }}
            </audit-menu-item>
            <audit-menu-item index="applicationManage">
              <audit-icon
                class="menu-item-icon"
                type="taocanchulizhong" />
              {{ t('处理套餐') }}
            </audit-menu-item>
          </audit-menu-item-group>
          <audit-menu-item-group>
            <template #title>
              <div>{{ t('接入') }}</div>
            </template>
            <template #flod-title>
              <div>{{ t('接入') }}</div>
            </template>
            <audit-menu-item index="systemManage">
              <audit-icon
                class="menu-item-icon"
                type="insert" />
              {{ t('系统接入') }}
            </audit-menu-item>
          </audit-menu-item-group>
          <audit-menu-item-group v-if="configData.super_manager">
            <template #title>
              <div>{{ t('管理') }}</div>
            </template>
            <template #flod-title>
              <div>{{ t('管理') }}</div>
            </template>
            <audit-menu-item index="storageManage">
              <audit-icon
                class="menu-item-icon"
                type="data-storage" />
              {{ t('数据存储') }}
            </audit-menu-item>
          </audit-menu-item-group>
        </template>
        <template v-else-if="curNavName === 'auditRiskManage'">
          <audit-menu-item index="handleManage">
            <audit-icon
              class="menu-item-icon"
              type="daiwochuli" />
            {{ t('待我处理') }}
          </audit-menu-item>
          <audit-menu-item index="attentionManage">
            <audit-icon
              class="menu-item-icon"
              type="wodeguanzhu" />
            {{ t('我的关注') }}
          </audit-menu-item>
          <audit-menu-item index="riskManage">
            <audit-icon
              class="menu-item-icon"
              type="gaojingshijian" />
            {{ t('所有风险') }}
          </audit-menu-item>
        </template>
        <template v-else-if="menuData.length">
          <audit-menu-item
            v-for="item in menuData"
            :key="item.id"
            :class="[item.id === route.params.id ? 'active' : '']"
            :index="item.id">
            <audit-icon
              class="menu-item-icon"
              type="baobiao" />
            {{ item.name }}
          </audit-menu-item>
        </template>
      </audit-menu>
    </template>
    <template #contentHeader>
      <slot name="back" />
    </template>
    <div>
      <slot />
    </div>
  </audit-navigation>
</template>
<script setup lang="ts">
  import {
    defineExpose,
    onBeforeUnmount,
    type Ref,
    ref,
    watch  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import ConfigModel from '@model/root/config';

  import useEventBus from '@hooks/use-event-bus';
  import useFeature from '@hooks/use-feature';
  import usePlatformConfig from '@hooks/use-platform-config';

  import AuditMenu from '@components/audit-menu/index.vue';
  import AuditMenuItem from '@components/audit-menu/item.vue';
  import AuditMenuItemGroup from '@components/audit-menu/item-group.vue';
  import AuditNavigation from '@components/audit-navigation/index.vue';

  interface Exposes {
    titleRef: Ref<string>
  }
  interface MenuDataType {
    id: string;
    name: string;
  }
  interface Props {
    configData: ConfigModel,
  }
  defineProps<Props>();
  const router = useRouter();
  const route = useRoute();
  const isMenuFlod = ref(false);
  const { on, off } = useEventBus();
  const { t } = useI18n();
  const curNavName = ref('');
  const handleSideMenuFlodChange = (value: boolean) => {
    isMenuFlod.value = !value;
  };

  const platformConfig = usePlatformConfig();

  // 是否展示审计报表导航
  const { feature: hasBkvision } = useFeature('bkvision');
  const titleRef = ref<string>('');
  const menuData = ref<Array<MenuDataType>>([]);
  on('statement-menuData', (data) => {
    menuData.value = data as Array<MenuDataType>;
    titleRef.value = menuData.value[0]?.name;
  });
  // 导航路由切换
  const handleRouterChange = (routerName: string) => {
    if (curNavName.value === 'auditStatement') {
      router.push({
        name: 'statementManageDetail',
        params: {
          id: routerName,
        },
      });
      titleRef.value = menuData.value.find(item => item.id === routerName)?.name || '';
      return;
    }
    router.push({
      name: routerName,
    });
  };
  watch(route, () => {
    curNavName.value = route.meta.navName as string;
  }, {
    deep: true,
    immediate: true,
  });
  onBeforeUnmount(() => {
    off('statement-menuData');
  });
  defineExpose<Exposes>({
    titleRef,
  });
</script>
<style lang="postcss">
#app {
  .site-title {
    padding-left: 16px;
    font-size: 16px;
    color: #eaebf0;
    word-break: keep-all;
    white-space: nowrap;
    cursor: pointer;
  }

  .main-navigation-left {
    .main-navigation-nav {
      margin-right: 32px;
      font-size: 14px;
      color: #94a2bb;
    }

    .main-navigation-nav.active {
      color: #fff;
    }
  }

}
</style>
