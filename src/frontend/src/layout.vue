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
        <a
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'auditRiskManage'
          }"
          :href="mainNavHref('handleManageList', 'auditRiskManage')"
          @click="handleMainNavClick($event, 'handleManageList', 'auditRiskManage')">
          {{ t('风险') }}
        </a>

        <a
          v-if="hasBkvision.enabled &&
            (userRole.includes('saas_admin') || userRole.includes('scene_user') || userRole.includes('scene_admin'))"
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'auditStatement'
          }"
          :href="mainNavHref('statementManage', 'auditStatement')"
          @click="handleMainNavClick($event, 'statementManage', 'auditStatement')">
          {{ t('报表') }}
        </a>
        <a
          v-if="!userRole.includes('risk_handler') &&
            (userRole.includes('saas_admin') || userRole.includes('scene_user') || userRole.includes('scene_admin'))"
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'toolsSquare'
          }"
          :href="mainNavHref('toolsSquare', 'toolsSquare')"
          @click="handleMainNavClick($event, 'toolsSquare', 'toolsSquare')">
          {{ t('工具广场') }}
        </a>
        <a
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'secChat'
          }"
          :href="mainNavHref('secChat', 'secChat')"
          @click="handleMainNavClick($event, 'secChat', 'secChat')">
          {{ t('AI助手') }}
        </a>
        <a
          v-if="userRolePermission.show_log_search"
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'auditConfigurationManage'
          }"
          :href="mainNavHref('analysisList', 'auditConfigurationManage')"
          @click="handleMainNavClick($event, 'analysisList', 'auditConfigurationManage')">
          {{ t('日志检索') }}
        </a>
        <!-- 风险使用者、系统管理员要跳转到应到页 -->
        <a
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'sceneConfiguration'
          }"
          :href="mainNavHref(sceneConfigRouterName, 'sceneConfiguration')"
          @click="handleMainNavClick($event, sceneConfigRouterName, 'sceneConfiguration')">
          {{ t('场景配置') }}
        </a>
        <a
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'nweSystemManage'
          }"
          :href="mainNavHref(systemHomeName, 'nweSystemManage')"
          @click="handleMainNavClick($event, systemHomeName, 'nweSystemManage')">
          {{ t('系统接入') }}
        </a>
        <a
          v-if="userRole.includes('saas_admin')"
          class="main-navigation-nav "
          :class="{
            active: curNavName === 'platformManage'
          }"
          :href="mainNavHref('platformSceneConfig', 'platformManage')"
          @click="handleMainNavClick($event, 'platformSceneConfig', 'platformManage')">
          {{ t('平台管理') }}
        </a>
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
        <template v-if="curNavName === 'sceneConfiguration'">
          <scene-config-sidebar />
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
            v-if="hasAllRiskPermission && userRole.includes('saas_admin')"
            index="confirmManage">
            <audit-icon
              class="menu-item-icon"
              type="gaojingshijian" />
            {{ t('待我确认') }}
          </audit-menu-item>
          <audit-menu-item
            v-if="(userRole.includes('saas_admin') ||
              userRole.includes('scene_admin') || userRole.includes('scene_user'))"
            index="sceneRiskManage">
            <audit-icon
              class="menu-item-icon"
              type="gaojingshijian" />
            {{ t('场景风险') }}
          </audit-menu-item>
          <audit-menu-item
            v-if="hasAllRiskPermission && userRole.includes('saas_admin')"
            index="riskManage">
            <audit-icon
              class="menu-item-icon"
              type="gaojingshijian" />
            {{ t('所有风险') }}
          </audit-menu-item>
        </template>
        <template v-else-if="curNavName === 'auditStatement'">
          <reports-sidebar :menu-data="menuData" />
        </template>
        <template v-else-if="curNavName === 'nweSystemManage'">
          <system-manage-sidebar />
          <!-- <div class="system-select">
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
            <div
              v-for="item in route.meta.sideMenus as unknown as SideMenuItem[]"
              :key="item.pathName"
              class="group">
              <audit-menu-item
                :index="item.pathName"
                is-self-router-change
                @self-router-change="selfRouterChange(item)">
                <audit-icon
                  class="menu-item-icon"
                  :type="item?.icon" />
                {{ t(item.title) }}
              </audit-menu-item>
            </div>
          </template> -->
        </template>
        <template v-else-if="curNavName === 'platformManage'">
          <platform-sidebar />
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
    computed,
    onBeforeUnmount,
    onMounted,
    type Ref,
    ref,
    watch  } from 'vue';
  // interface SideMenuItem {
  //   pathName: string;
  //   icon: string;
  //   title: string;
  //   groupName: string
  // }
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import IamManageService from '@service/iam-manage';
  import MetaManageService from '@service/meta-manage';

  // import ConfigModel from '@model/root/config';
  import useEventBus from '@hooks/use-event-bus';
  import useFeature from '@hooks/use-feature';
  import usePlatformConfig from '@hooks/use-platform-config';

  import AuditMenu from '@components/audit-menu/index.vue';
  import AuditMenuItem from '@components/audit-menu/item.vue';
  import AuditMenuItemGroup from '@components/audit-menu/item-group.vue';
  import AuditNavigation from '@components/audit-navigation/index.vue';

  // import Tooltips from '@components/show-tooltips-text/index.vue';
  import systemHeaderTips from '@views/new-system-manage/system-info/components/header-tips.vue';

  import PlatformSidebar from '@/components/statement-sidebar/platfrom.vue';
  import ReportsSidebar from '@/components/statement-sidebar/reports.vue';
  import SceneConfigSidebar from '@/components/statement-sidebar/scene-config.vue';
  import SystemManageSidebar from '@/components/statement-sidebar/system-manage.vue';
  import useRequest from '@/hooks/use-request';

  interface Exposes {
    titleRef: Ref<string>
    descriptionRef: Ref<string>
    currentPanelScene: Ref<{ id: string; name: string; type: string } | null>
  }
  interface MenuDataType {
    id: string;
    name: string;
    description?: string;
    group_ids: number[];
    priority_index?: number;
    favorite_created_at?: string | null;
  }
  // interface Props {
  //   configData: ConfigModel,
  // }

  // defineProps<Props>();

  const router = useRouter();
  const route = useRoute();
  const { on, off, emit } = useEventBus();
  const platformConfig = usePlatformConfig();
  const { t } = useI18n();

  const userRole = JSON.parse(sessionStorage.getItem('userRole') || '["risk_handler"]') as string[];
  const userRolePermission = JSON.parse(sessionStorage.getItem('userScenePermission') || '{}') as Record<string, string[]>;

  // 是否展示审计报表导航
  const { feature: hasBkvision } = useFeature('bkvision');

  const isMenuFlod = ref(false);
  const curNavName = ref('');
  const titleRef = ref<string>('');
  const descriptionRef = ref<string>('');
  // 聚合模式下当前面板所属场景信息（供 header 显示场景标签）
  const currentPanelScene = ref<{ id: string; name: string; type: string } | null>(null);
  // 从 scene-system-selector 缓存的稳定场景列表
  const cachedSceneList = ref<Array<{ id: string; name: string; type: string }>>([]);
  // 尝试从 localStorage 恢复已缓存的 sceneList
  try {
    const saved = JSON.parse(localStorage.getItem('scene-system-selector:sceneList') || '[]');
    if (Array.isArray(saved)) {
      cachedSceneList.value = saved;
    }
  } catch { /* ignore */ }
  const menuData = ref<Array<MenuDataType>>([]);
  // const systemId = ref<string | null>(null);
  // 项目列表
  // interface SystemItem {
  //   id: string;
  //   name: string;
  //   permission: {
  //     view_system: boolean;
  //   };
  //   permission_type: 'simple' | 'complex';
  //   system_status: 'pending' | 'incomplete' | 'abnormal' | 'normal';
  //   system_stage?: 'pending' | 'permission_model' | 'collector' | 'completed';
  //   favorite: boolean;
  // }

  // const projectList = ref<SystemItem[]>([]);
  // const permissionCreateSystem = ref(false);
  // 系统列表是否为空（用于决定跳转引导页还是列表页）
  const isSystemListEmpty = ref(true);
  const systemHomeName = computed(() => (
    (isSystemListEmpty.value || !(userRole.includes('saas_admin') || userRole.includes('system_admin')))
      ? 'systemLandingPage'
      : 'systemList'
  ));

  // const contentText = (stage: string | undefined) => {
  //   if (stage === 'permission_model') {
  //     return t('系统尚未完成确实模型配置，请继续设置');
  //   } if (stage === 'collector') {
  //     return t('系统尚未完成日志数据上报，请继续上报');
  //   }
  //   return '';
  // };
  // const isSelectOpen = ref(false);

  // const handleSelectToggle = (val: boolean) => {
  //   isSelectOpen.value = val;
  // };
  // 计算属性根据 userRole 计算sceneConfigRouterName
  const sceneConfigRouterName = computed(() => {
    if (userRole.includes('saas_admin') || userRole.includes('scene_admin')) { // 管理员 和 场景管理员
      return 'sceneInfo';
    }
    if (userRole.includes('risk_handler')) {  // 风险处理人
      return 'landingPage';
    }
    if (userRole.includes('system_admin') || userRole.includes('scene_user')) { //  系统管理员 场景使用者
      return 'userLandingPage';
    }
    return 'landingPage';
  });

  const pickSceneQuery = () => {
    const query = route.query as Record<string, unknown>;
    const scope: Record<string, string> = {};
    ['scene_id', 'scope_id', 'scope_type'].forEach((key) => {
      const value = query[key];
      if (value === undefined || value === null || value === '') return;
      scope[key] = Array.isArray(value) ? String(value[0]) : String(value);
    });
    return scope;
  };

  /**
   * 顶栏点击的目标页。已经停在该菜单首页时返回 null。
   * 不把 query 清成空对象，否则场景选择器会立刻把场景参数写回去，把这次跳转取消。
   */
  const resolveMainNavLocation = (homeName: string, navName: string) => {
    const query = pickSceneQuery();
    const alreadyInNav = curNavName.value === navName;
    const currentName = String(route.name || '');

    if (homeName === 'secChat') {
      // 父路由会重定向到上次会话。已在该页时由导航重复错误吞掉，不另改成空白首页。
      return { name: 'secChat' };
    }

    if (homeName === 'statementManage') {
      if (!alreadyInNav) return { name: 'statementManage', query };
      const firstId = menuData.value[0]?.id;
      if (!firstId) {
        return currentName === 'statementManage' ? null : { name: 'statementManage', query };
      }
      if (currentName === 'statementManageDetail' && String(route.params.id || '') === String(firstId)) {
        return null;
      }
      return {
        name: 'statementManageDetail',
        params: { id: String(firstId) },
        query,
      };
    }

    if (homeName === 'toolsSquare' && alreadyInNav) {
      return currentName === 'toolsSquare' ? null : { name: 'toolsSquare', query };
    }

    const homeAliases: Record<string, string[]> = {
      handleManageList: ['handleManage', 'handleManageList'],
      analysisList: ['analysisManage', 'analysisList'],
      platformSceneConfig: ['platformManage', 'platformSceneConfig'],
    };
    const homeNames = homeAliases[homeName] || [homeName];
    if (alreadyInNav && homeNames.includes(currentName)) return null;
    return { name: homeName, query };
  };

  const mainNavHref = (homeName: string, navName: string) => {
    const location = resolveMainNavLocation(homeName, navName)
      || { name: homeName, query: pickSceneQuery() };
    return router.resolve(location).href;
  };

  const handleMainNavClick = (event: MouseEvent, homeName: string, navName: string) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    // 工作台和广场共用页面实例。从本菜单或其他菜单进入时，都先回到广场列表，
    // 已打开的工具留在「正在使用」里，不自动打开工作台。
    if (homeName === 'toolsSquare') {
      emit('tools-square:go-home');
    }
    const location = resolveMainNavLocation(homeName, navName);
    if (!location) return;
    router.push(location).catch(() => {});
  };
  // // 获取新建权限
  // useRequest(IamManageService.check, {
  //   defaultParams: {
  //     action_ids: 'create_system',
  //   },
  //   defaultValue: {},
  //   manual: true,
  //   onSuccess: (data) => {
  //     permissionCreateSystem.value = data.create_system;
  //   },
  // });

  // 获取系统列表，判断是否为空以决定跳转目标
  useRequest(MetaManageService.fetchSystemList, {
    defaultValue: { total: 0 } as { total: number },
    manual: true,
    defaultParams: {
      audit_status: 'accessed',
      filter_actions: 'edit_system,view_system',
    },
    onSuccess: (data: any) => {
      isSystemListEmpty.value = data.total === 0;
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

  // // 检查平台管理权限
  // const hasPlatformManagePermission = ref(false);
  // useRequest(IamManageService.check, {
  //   defaultParams: {
  //     action_ids: 'manage_platform',
  //   },
  //   defaultValue: {},
  //   manual: true,
  //   onSuccess: (data) => {
  //     hasPlatformManagePermission.value = data.manage_platform || false;
  //   },
  // });

  // const {
  //   run: fetchSystemWithAction,
  // } = useRequest(MetaManageService.fetchSystemWithAction, {
  //   defaultValue: [],
  //   onSuccess: (data: any[]) => {
  //     projectList.value = data;
  //     if (route.params.id) {
  //       systemId.value = route.params.id as string;
  //     } else {
  //       systemId.value = sessionStorage.getItem('systemProjectId') || data[0].id;
  //       if (route.name === 'systemInfo') {
  //         router.push({
  //           name: 'systemInfo',
  //           params: {
  //             id: systemId.value,
  //           },
  //         });
  //       }
  //     }
  //   },
  // });

  on('statement-menuData', (data) => {
    menuData.value = data as Array<MenuDataType>;
    if (route.params.id) {
      const matched = menuData.value.find(item => item.id === route.params.id);
      titleRef.value = matched?.name || '';
      descriptionRef.value = matched?.description || '';
    } else {
      titleRef.value =  menuData.value[0]?.name;
      descriptionRef.value = menuData.value[0]?.description || '';
    }
  });

  // 聚合模式下监听当前面板所属场景变化
  on('panel-scene-change', (scene) => {
    currentPanelScene.value = scene as { id: string; name: string; type: string } | null;
    // 缓存到 sessionStorage，刷新后可恢复
    sessionStorage.setItem('layout:currentPanelScene', JSON.stringify(scene));
  });

  // 监听 scene-system-selector 的 sceneList 就绪事件（稳定数据源，刷新也可用）
  on('scene-list-ready', (list) => {
    cachedSceneList.value = list as Array<{ id: string; name: string; type: string }>;
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
        query: route.query, // ⚠️ 保留现有 query 参数（包括 scene_id）
      });
      titleRef.value = menuData.value.find(item => item.id === routerName)?.name || '';
      return;
    }
    if (routerName === 'systemAccess') {
      // sessionStorage.setItem('systemProjectId', systemId.value || '');
      const routePath = router.resolve({ name: routerName }).href;
      window.open(routePath, '_blank');
      return;
    }
    if (routerName === 'toolsSquare' && curNavName.value === 'toolsSquare') {
      emit('tools-square:go-home');
      if (route.name === 'toolsSquare') return;
      router.push({
        name: 'toolsSquare',
        query: pickSceneQuery(),
      }).catch(() => {});
      return;
    }
    router.push({
      name: routerName,
    });
  };

  // // 系统切换
  // const handleSystemChange = (value: string) => {
  //   // 找到对应选中item
  //   const project = projectList.value.find(item => item.id === value);
  //   if (!project) {
  //     return;
  //   }
  //   // 在route.meta中添加systemId
  //   sessionStorage.setItem('systemProjectId', value);
  //   router.push({
  //     name: 'systemInfo',
  //     params: {
  //       id: value,
  //     },
  //     query: {
  //       type: project.permission_type,
  //     },
  //   });
  // };

  // // 更新系统收藏
  // const {
  //   run: fetchSystemAuditFavoriteUpdate,
  // } = useRequest(MetaManageService.fetchSystemAuditFavoriteUpdate, {
  //   defaultValue: {},
  // });
  // const selfRouterChange = (item: SideMenuItem) => {
  //   router.push({
  //     name: item.pathName,
  //     params: {
  //       id: systemId.value,
  //     },
  //   });
  // };
  // // 系统收藏
  // const handlerFavorite = (item: Record<string, any>, val: boolean) => {
  //   fetchSystemAuditFavoriteUpdate({
  //     system_id: item.id,
  //     favorite: val,
  //   }).then(() => {
  //     projectList.value = projectList.value.map((i) => {
  //       if (i.id === item.id) {
  //         return {
  //           ...i,
  //           favorite: val,
  //         };
  //       }
  //       return i;
  //     });
  //   });
  // };
  watch(route, () => {
    curNavName.value = route.meta.navName as string;
    // 切换菜单项时同步更新 descriptionRef
    if (curNavName.value === 'auditStatement' && route.params.id && menuData.value.length > 0) {
      const matched = menuData.value.find(item => item.id === route.params.id);
      titleRef.value = matched?.name || '';
      descriptionRef.value = matched?.description || '';
    }
    // 切换单场景时立即清除场景标签（scope_type 不再是 cross_scene/cross_system）
    const isAggregateMode = route.query.scope_type === 'cross_scene'
      || route.query.scope_type === 'cross_system';
    if (curNavName.value === 'auditStatement' && !isAggregateMode) {
      currentPanelScene.value = null;
    }
    // 聚合模式下，刷新页面时从 sessionStorage 恢复场景标签
    if (curNavName.value === 'auditStatement'
      && !currentPanelScene.value
      && isAggregateMode) {
      try {
        const saved = JSON.parse(sessionStorage.getItem('layout:currentPanelScene') || 'null');
        if (saved) {
          currentPanelScene.value = saved;
        }
      } catch { /* ignore */ }
    }
  }, {
    deep: true,
    immediate: true,
  });


  onMounted(() => {
    // fetchSystemWithAction({
    //   sort_keys: 'favorite,permission',
    //   action_ids: 'view_system',
    //   with_favorite: true,
    //   with_system_status: true,
    //   audit_status__in: 'accessed',
    // });
  }),
  onBeforeUnmount(() => {
    off('statement-menuData');
  });

  defineExpose<Exposes>({
    titleRef,
    descriptionRef,
    currentPanelScene,
  });
</script>
<style lang="postcss">
#app {
  .site-title {
    padding-left: var(--bk-theme-space-16);
    font-size: var(--bk-theme-font-size-lg);
    color: var(--bk-theme-nav-top-text-active);
    word-break: keep-all;
    white-space: nowrap;
    cursor: pointer;
  }

  .main-navigation-left {
    display: flex;
    align-items: stretch;
    height: var(--bk-theme-nav-height);

    .main-navigation-nav {
      position: relative;
      display: inline-flex;
      align-items: center;
      height: var(--bk-theme-nav-height);
      margin-right: var(--bk-theme-space-32);
      font-size: var(--bk-theme-font-size-base);
      color: var(--bk-theme-nav-top-text);
    }

    .main-navigation-nav.active {
      color: var(--bk-theme-nav-top-text-active);
    }

    .main-navigation-nav.active::after {
      position: absolute;
      right: 0;
      bottom: var(--bk-theme-nav-indicator-offset);
      left: 0;
      height: var(--bk-theme-nav-indicator-height);
      background: var(--bk-theme-nav-indicator);
      border-radius: var(--bk-theme-nav-indicator-radius);
      content: '';
    }
  }

  .system-select {
    width: 90%;margin-top: var(--bk-theme-space-8);
    margin-left: 5%;

    .bk-input {
      border: 1px solid var(--bk-theme-nav-side-border);
      box-shadow: none;

      .bk-input--text {
        color: var(--bk-theme-nav-side-text);
        background-color: var(--bk-theme-surface-default);
      }
    }
  }
}

.system-select-popover.bk-popover.bk-pop2-content[data-theme^='light'] {
  color: var(--bk-theme-text-default);
  background-color: var(--bk-theme-surface-default);
  border-color: var(--bk-theme-nav-side-border);
  box-shadow: var(--bk-theme-overlay-shadow);

  .bk-select-content-wrapper {
    .bk-select-search-wrapper {
      border-bottom: 1px solid var(--bk-theme-nav-side-border);

      .bk-select-search-input {
        color: var(--bk-theme-text-default);
        background-color: var(--bk-theme-surface-default);
      }
    }
  }

  .bk-select-content {
    .bk-select-option.is-hover {
      background-color: var(--bk-theme-surface-subtle);
    }

    .is-selected:not(.is-checkbox) {
      color: var(--bk-theme-nav-side-text-active);
      background-color: var(--bk-theme-fill-selected) !important;
    }

    .popover {
      position: relative;
      display: flex;
      width: 100%;
      align-items: center;  /* 垂直居中 */
      justify-content: space-between;  /* 两端对齐 */

      .pentagram-fill {
        width: 14px;
        height: 14px;margin-left: var(--bk-theme-space-8);  /* 添加左边距 */
        cursor: pointer;
      }
    }

    .bk-select-extension {
      border: none;

      .custom-extension {
        display: flex;
        width: 100%;
        height: 100%;padding: 0 var(--bk-theme-space-8);
        font-size: 12px;
        color: var(--bk-theme-text-default);
        background-color: var(--bk-theme-surface-muted);
        align-items: center;  /* 垂直居中 */
        justify-content: center;  /* 水平居中 */
        gap: 4px;  /* 图标和文字间距 */
        border: none;
        border-radius: 0;

        .custom-extension-icon {padding: var(--bk-theme-space-2);margin-right: var(--bk-theme-space-8);
          font-size: 8px;
          color: var(--bk-theme-text-disabled);
          border: 1px solid var(--bk-theme-text-disabled);
          border-radius: var(--bk-theme-radius-full);
        }
      }
    }
  }
}

.group {margin-top: var(--bk-theme-space-8);
}
</style>
