/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/
import { computed } from 'vue';
import {
  useRoute,
  useRouter,
} from 'vue-router';
import type {
  RouteLocationNormalizedLoaded,
  Router,
} from 'vue-router';

type ReadyRoute = RouteLocationNormalizedLoaded | ReturnType<Router['resolve']>;

/**
 * 首屏守卫还没放行时，当前 route.meta 是空的。
 * 用地址直接匹配路由表，侧栏按目标页的 hideSidebar / nodeSideContent / navName 画，不先出空白菜单。
 */
export const resolveReadyRoute = (
  route: RouteLocationNormalizedLoaded,
  router: Router,
): ReadyRoute => {
  if (route.matched.length > 0) {
    return route;
  }
  return router.resolve(window.location.pathname);
};

/** 侧栏、顶栏菜单和页面槽位共用这一份，刷新时不会各判各的。 */
export const useReadyRoute = () => {
  const route = useRoute();
  const router = useRouter();
  const readyRoute = computed(() => resolveReadyRoute(route, router));
  const showSideBarParam = computed(() => readyRoute.value.params?.isShowSideBar === 'true');
  const showNodeSide = computed(() => (
    Boolean(readyRoute.value.meta?.nodeSideContent) && !showSideBarParam.value
  ));
  const hideSidebar = computed(() => Boolean(readyRoute.value.meta?.hideSidebar));

  return {
    readyRoute,
    showSideBarParam,
    showNodeSide,
    hideSidebar,
  };
};
