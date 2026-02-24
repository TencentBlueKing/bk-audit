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
    <template #headerTips>
      <system-header-tips v-if="route.meta?.headerTips === 'systemInfo'" />
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
            active: curNavName === 'toolsSquare'
          }"
          :to="{ name:'toolsSquare', query: {} }">
          {{ t('工具广场') }}
        </router-link>
        <router-link
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'auditConfigurationManage'
          }"
          :to="{ name:'analysisManage', query: {} }">
          {{ t('审计配置') }}
        </router-link>
        <router-link
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'nweSystemManage'
          }"
          :to="{ name:'nweSystemManage', params: {
            id: systemId
          } }">
          {{ t('系统管理') }}
        </router-link>
      </div>
    </template>
    <template #headerRight>
      <slot name="headerRight" />
    </template>
    <template #nodeSideContent>
      <slot name="nodeSideContent" />
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
              {{ t('系统列表') }}
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
        <template v-else-if="curNavName === 'toolsSquare'">
          <audit-menu-item-group>
            <template #title>
              <div>{{ t('工具广场') }}</div>
            </template>
            <template #flod-title>
              <div>{{ t('工具广场') }}</div>
            </template>
            <audit-menu-item index="toolsSquare">
              <audit-icon
                class="menu-item-icon"
                type="gongju" />
              {{ t('工具广场') }}
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
          <audit-menu-item index="processedManage">
            <audit-icon
              class="menu-item-icon"
              type="yunxingjilu" />
            {{ t('处理历史') }}
          </audit-menu-item>
          <audit-menu-item index="attentionManage">
            <audit-icon
              class="menu-item-icon"
              type="wodeguanzhu" />
            {{ t('我的关注') }}
          </audit-menu-item>
          <audit-menu-item
            v-if="hasAllRiskPermission"
            index="riskManage">
            <audit-icon
              class="menu-item-icon"
              type="gaojingshijian" />
            {{ t('所有风险') }}
          </audit-menu-item>
        </template>
        <template v-else-if="menuData.length && curNavName === 'auditStatement'">
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
        <template v-else-if="curNavName === 'nweSystemManage'">
          <div class="system-select">
            <bk-select
              v-model="systemId"
              auto-focus
              class="bk-select"
              :clearable="false"
              filterable
              :popover-options="{
                extCls: 'system-select-popover',
                width: '320px'
              }"
              :search-with-pinyin="false"
              @change="handleSystemChange"
              @toggle="handleSelectToggle">
              <bk-option
                v-for="item in projectList"
                :id="item.id"
                :key="item.id"
                :disabled="!(item.permission.view_system)"
                :name="`${item.name}(${item.id})`">
                <div
                  class="popover"
                  :style="item.permission.view_system ? `color: #C4C6CC;` : `color: #70737A;`">
                  <div style="display: flex;">
                    <tooltips
                      v-if="isSelectOpen"
                      :data="`${item.name}(${item.id})`"
                      style="max-width: 200px;"
                      theme="light" />
                    <bk-popover
                      v-if="item.system_status === 'incomplete'"
                      :content="contentText(item.system_stage)"
                      placement="top"
                      theme="light">
                      <bk-tag
                        size="small"
                        style="margin-left: 8px;"
                        theme="warning"
                        type="filled">
                        {{ t('待完善') }}
                      </bk-tag>
                    </bk-popover>
                    <bk-tag
                      v-if="item.system_status === 'abnormal'"
                      size="small"
                      style="margin-left: 8px;"
                      theme="danger"
                      type="filled">
                      {{ t('数据异常') }}
                    </bk-tag>
                  </div>
                  <div>
                    <span v-if="item.permission.view_system">
                      <img
                        v-if="item.favorite"
                        class="pentagram-fill"
                        src="@images/pentagram-fill.svg"
                        @click.stop="handlerFavorite(item,false)">
                      <img
                        v-if="!(item.favorite)"
                        class="pentagram-fill"
                        src="@images/pentagram.svg"
                        style="color: #4d4f56;"
                        @click.stop="handlerFavorite(item,true)">
                    </span>
                    <span v-else>
                      <auth-component
                        action-id="view_system"
                        :permission="item.permission.view_system"
                        :resource="item.id"
                        style="cursor: pointer;">
                        <img
                          v-if="!(item.permission.view_system)"
                          class="pentagram-fill"
                          src="@images/lock-1.svg">
                      </auth-component>
                    </span>
                  </div>
                </div>
              </bk-option>

              <template #extension>
                <bk-button
                  class="custom-extension"
                  :disabled="!permissionCreateSystem"
                  @click="handleRouterChange('systemAccess')">
                  <audit-icon
                    class="custom-extension-icon"
                    type="add" />
                  <span
                    v-if="permissionCreateSystem"
                    class="extension-text"
                    style="color: #c4c6cc;">{{ t('接入新系统') }}</span>
                  <bk-popover
                    v-else
                    :content="t('暂无权限')"
                    placement="top"
                    theme="light">
                    <span
                      class="extension-text"
                      style="color: #c4c6cc;">{{ t('接入新系统') }}</span>
                  </bk-popover>
                </bk-button>
              </template>
            </bk-select>
          </div>
          <template v-if="route.meta.isGroup">
            <audit-menu-item-group
              v-for="item in route.meta.sideMenus as unknown as SideMenuItem[]"
              :key="item.pathName">
              <template #title>
                <div>{{ t(item.groupName) }}</div>
              </template>
              <template #flod-title>
                <div>{{ t(item.groupName) }}</div>
              </template>
              <audit-menu-item
                :index="item.pathName"
                is-self-router-change
                @self-router-change="selfRouterChange(item)">
                <audit-icon
                  class="menu-item-icon"
                  :type="item?.icon" />
                {{ t(item.title) }}
              </audit-menu-item>
            </audit-menu-item-group>
          </template>
          <template v-else>
            //
          </template>
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
    onBeforeUnmount,
    onMounted,
    type Ref,
    ref,
    watch  } from 'vue';

  interface SideMenuItem {
    pathName: string;
    icon: string;
    title: string;
    groupName: string
  }
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import MetaManageService from '@service/meta-manage';

  import ConfigModel from '@model/root/config';

  import useEventBus from '@hooks/use-event-bus';
  import useFeature from '@hooks/use-feature';
  import usePlatformConfig from '@hooks/use-platform-config';

  import AuditMenu from '@components/audit-menu/index.vue';
  import AuditMenuItem from '@components/audit-menu/item.vue';
  import AuditMenuItemGroup from '@components/audit-menu/item-group.vue';
  import AuditNavigation from '@components/audit-navigation/index.vue';
  import Tooltips from '@components/show-tooltips-text/index.vue';

  import systemHeaderTips from '@views/new-system-manage/system-info/components/header-tips.vue';

  import useRequest from '@/hooks/use-request';

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
  const { on, off } = useEventBus();
  const platformConfig = usePlatformConfig();
  const { t } = useI18n();

  // 是否展示审计报表导航
  const { feature: hasBkvision } = useFeature('bkvision');

  const isMenuFlod = ref(false);
  const curNavName = ref('');
  const titleRef = ref<string>('');
  const menuData = ref<Array<MenuDataType>>([]);
  const systemId = ref<string | null>(null);
  // 项目列表
  interface SystemItem {
    id: string;
    name: string;
    permission: {
      view_system: boolean;
    };
    permission_type: 'simple' | 'complex';
    system_status: 'pending' | 'incomplete' | 'abnormal' | 'normal';
    system_stage?: 'pending' | 'permission_model' | 'collector' | 'completed';
    favorite: boolean;
  }

  const projectList = ref<SystemItem[]>([]);
  const permissionCreateSystem = ref(false);

  const contentText = (stage: string | undefined) => {
    if (stage === 'permission_model') {
      return t('系统尚未完成确实模型配置，请继续设置');
    } if (stage === 'collector') {
      return t('系统尚未完成日志数据上报，请继续上报');
    }
    return '';
  };
  const isSelectOpen = ref(false);

  const handleSelectToggle = (val: boolean) => {
    isSelectOpen.value = val;
  };
  // 获取新建权限
  useRequest(IamManageService.check, {
    defaultParams: {
      action_ids: 'create_system',
    },
    defaultValue: {},
    manual: true,
    onSuccess: (data) => {
      permissionCreateSystem.value = data.create_system;
    },
  });

  // 检查所有风险权限
  const hasAllRiskPermission = ref(false);
  useRequest(IamManageService.checkAny, {
    defaultParams: {
      action_ids: 'list_risk_v2',
    },
    defaultValue: {},
    manual: true,
    onSuccess: (data) => {
      hasAllRiskPermission.value = data.list_risk_v2 || false;
    },
  });

  const {
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    onSuccess: (data: any[]) => {
      projectList.value = data;
      if (route.params.id) {
        systemId.value = route.params.id as string;
      } else {
        systemId.value = sessionStorage.getItem('systemProjectId') || data[0].id;
        if (route.name === 'systemInfo') {
          router.push({
            name: 'systemInfo',
            params: {
              id: systemId.value,
            },
          });
        }
      }
    },
  });

  on('statement-menuData', (data) => {
    menuData.value = data as Array<MenuDataType>;
    if (route.params.id) {
      titleRef.value = menuData.value.find(item => item.id === route.params.id)?.name || '';
    } else {
      titleRef.value =  menuData.value[0]?.name;
    }
  });

  const handleSideMenuFlodChange = (value: boolean) => {
    isMenuFlod.value = !value;
  };

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
    if (routerName === 'systemAccess') {
      sessionStorage.setItem('systemProjectId', systemId.value || '');
      const routePath = router.resolve({ name: routerName }).href;
      window.open(routePath, '_blank');
      return;
    }
    router.push({
      name: routerName,
    });
  };

  // 系统切换
  const handleSystemChange = (value: string) => {
    // 找到对应选中item
    const project = projectList.value.find(item => item.id === value);
    if (!project) {
      return;
    }
    // 在route.meta中添加systemId
    sessionStorage.setItem('systemProjectId', value);
    router.push({
      name: 'systemInfo',
      params: {
        id: value,
      },
      query: {
        type: project.permission_type,
      },
    });
  };

  // 更新系统收藏
  const {
    run: fetchSystemAuditFavoriteUpdate,
  } = useRequest(MetaManageService.fetchSystemAuditFavoriteUpdate, {
    defaultValue: {},
  });
  const selfRouterChange = (item: SideMenuItem) => {
    router.push({
      name: item.pathName,
      params: {
        id: systemId.value,
      },
    });
  };
  // 系统收藏
  const handlerFavorite = (item: Record<string, any>, val: boolean) => {
    fetchSystemAuditFavoriteUpdate({
      system_id: item.id,
      favorite: val,
    }).then(() => {
      projectList.value = projectList.value.map((i) => {
        if (i.id === item.id) {
          return {
            ...i,
            favorite: val,
          };
        }
        return i;
      });
    });
  };
  watch(route, () => {
    curNavName.value = route.meta.navName as string;
  }, {
    deep: true,
    immediate: true,
  });


  onMounted(() => {
    fetchSystemWithAction({
      sort_keys: 'favorite,permission',
      action_ids: 'view_system',
      with_favorite: true,
      with_system_status: true,
      audit_status__in: 'accessed',
    });
  }),
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

  .system-select {
    width: 90%;
    margin-top: 10px;
    margin-left: 5%;

    .bk-input {
      border: none;
      box-shadow: none;

      .bk-input--text {
        color: #979ba5;
        background-color: #40495e;
      }
    }
  }
}

.system-select-popover.bk-popover.bk-pop2-content[data-theme^='light'] {
  color: #979ba5;
  background-color: #182233;
  border-color: #182233;
  box-shadow: none;

  .bk-select-content-wrapper {
    .bk-select-search-wrapper {
      border-bottom: 1px solid #3c4558;

      .bk-select-search-input {
        color: #c4c6cc;
        background-color: #182233;
      }
    }
  }

  .bk-select-content {
    .bk-select-option.is-hover {
      background-color: #2d3542;
    }

    .is-selected:not(.is-checkbox) {
      background-color: #294066 !important;
    }

    .popover {
      position: relative;
      display: flex;
      width: 100%;
      align-items: center;  /* 垂直居中 */
      justify-content: space-between;  /* 两端对齐 */

      .pentagram-fill {
        width: 14px;
        height: 14px;
        margin-left: 8px;  /* 添加左边距 */
        cursor: pointer;
      }
    }

    .bk-select-extension {
      border: none;

      .custom-extension {
        display: flex;
        width: 100%;
        height: 100%;
        padding: 0 10px;
        font-size: 12px;
        background-color: #28354d;
        align-items: center;  /* 垂直居中 */
        justify-content: center;  /* 水平居中 */
        gap: 4px;  /* 图标和文字间距 */
        border: none;
        border-radius: 0;

        .custom-extension-icon {
          padding: 2px;
          margin-right: 10px;
          font-size: 8px;
          color: #c4c6cc;
          border: 1px solid #c4c6cc;
          border-radius: 50%;
        }
      }
    }
  }
}
</style>
