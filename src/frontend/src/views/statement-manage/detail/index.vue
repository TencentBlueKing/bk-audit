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
  <div style="width: 100%;height: 100%;">
    <div id="panel" />
  </div>
</template>
<script setup lang="ts">
  import {
    nextTick,
    onUnmounted,
    watch,
  } from 'vue';
  import {
    useRoute,
  } from 'vue-router';

  import IamApplyDataModel from '@model/iam/apply-data';
  import ReportConfigService from '@service/report-config';
  import ToolManageService from '@service/tool-manage';

  import useMessage from '@hooks/use-message';

  import useEventBus from '@/hooks/use-event-bus';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  interface Error {
    data: Record<string, any>,
    message: string,
    status: number
  }

  const BKVISION_SCRIPT_SRC = 'https://staticfile.qq.com/bkvision/pbb9b207ba200407982a9bd3d3f2895d4/latest/main.js';

  const route = useRoute();
  const { messageError } = useMessage();
  const {  emit } = useEventBus();
  let app: any;
  // 取消过期的并发 init，避免先完成的请求覆盖正确图表
  let initSeq = 0;
  let lastInitKey = '';
  /** 进行中的 SDK 实例（尚未赋给 app），用于并发时能正确销毁 */
  let pendingInstance: any = null;

  // 校验id是否为有效值
  const isValidId = (id: any): boolean => {
    if (!id) return false;
    if (id === 'undefined' || id === 'null') return false;
    if (typeof id === 'string' && id.trim() === '') return false;
    return true;
  };

  const loadScript = (src: string) => new Promise((resolve, reject) => {
    if (window.BkVisionSDK) {
      resolve(undefined);
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve(script);
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
    document.head.appendChild(script);
  });

  const handleError = (_type: 'dashboard' | 'chart' | 'action' | 'others', err: Error) => {
    if (err?.data?.code === '9900403') {
      const iamResult = new IamApplyDataModel(err.data.data || {});
      // 页面展示没权限提示
      emit('permission-page', iamResult);
    } else if (err?.message) {
      messageError(err.message);
    }
  };

  const getQueryString = (value: unknown) => {
    if (Array.isArray(value)) {
      return value[0] ? String(value[0]) : '';
    }
    return value ? String(value) : '';
  };

  const getScopeConstants = () => {
    // 平台管理跳转会带 scope 查询参数，优先于 localStorage，避免新开页被全局选择覆盖
    const queryScopeId = getQueryString(route.query.scope_id);
    const querySceneId = getQueryString(route.query.scene_id);
    const queryScopeType = getQueryString(route.query.scope_type);

    if (queryScopeType === 'cross_scene' || querySceneId === 'allSecen') {
      return {
        scope_type: 'cross_scene',
        scope_id: '',
      };
    }
    if (queryScopeType === 'cross_system' || querySceneId === 'allSystem') {
      return {
        scope_type: 'cross_system',
        scope_id: '',
      };
    }
    if (queryScopeType === 'system' && queryScopeId) {
      return {
        scope_type: 'system',
        scope_id: queryScopeId,
      };
    }
    if (queryScopeType === 'scene' && (queryScopeId || querySceneId)) {
      return {
        scope_type: 'scene',
        scope_id: queryScopeId || querySceneId,
      };
    }
    if (querySceneId) {
      return {
        scope_type: 'scene',
        scope_id: querySceneId,
      };
    }

    return {
      scope_type: getSceneSystemParams().scope_type,
      scope_id: getSceneSystemParams().scope_id,
    };
  };

  const buildInitKey = (scope: { scope_type: string, scope_id: string }) => (
    `${String(route.params.id)}|${scope.scope_type}|${scope.scope_id}`
  );

  // 按当前 scope 拉取平台报表配置的默认值覆盖（失败不影响出图）
  // 与工具详情一致：由接口按 scope 合并 default + scenes/systems 后返回单份 default_value_override
  const fetchPanelDetailWithOverride = async (scope: {
    scope_type: string,
    scope_id: string,
  }) => {
    if (!scope.scope_type || !scope.scope_id) {
      return {
        vision_id: '',
        default_value_override: {} as Record<string, any>,
      };
    }
    try {
      const detail = await ReportConfigService.fetchPanelDetail({
        panel_id: String(route.params.id),
        scope_type: scope.scope_type,
        scope_id: String(scope.scope_id),
      });
      return {
        vision_id: detail?.vision_id || '',
        default_value_override: detail?.default_value_override || {},
      };
    } catch (e) {
      console.error('获取报表默认值覆盖失败:', e);
      return {
        vision_id: '',
        default_value_override: {} as Record<string, any>,
      };
    }
  };

  /**
   * 从 share_detail 解析变量 / 交互组件 flag 集合
   * 与报表配置、BKVision 工具一致：variable → constants，其余 → filters
   */
  const resolveParamFlagSets = async (visionId: string) => {
    const variableFlags = new Set<string>();
    const filterFlags = new Set<string>();

    if (!visionId) {
      return { variableFlags, filterFlags };
    }

    try {
      const res = await ToolManageService.fetchReportLists({ share_uid: visionId });
      if (!res?.data) {
        return { variableFlags, filterFlags };
      }

      const panels = Array.isArray(res.data.panels) ? res.data.panels : [];
      const variables = Array.isArray(res.data.variables) ? res.data.variables : [];
      const shareFilters = res.filters || {};
      const shareConstants = res.constants || {};

      Object.keys(shareFilters).forEach((uid) => {
        const panel = panels.find((item: any) => item.uid === uid);
        const flag = panel?.chartConfig?.flag;
        if (flag) {
          filterFlags.add(flag);
        }
      });

      variables.forEach((item: any) => {
        if (!item.build_in && item.flag) {
          variableFlags.add(item.flag);
        }
      });

      // variables 为空时，constants 中的非内置项按变量处理
      if (variables.length === 0) {
        Object.keys(shareConstants).forEach((flag) => {
          if (flag && !flag.startsWith('bkv_')) {
            variableFlags.add(flag);
          }
        });
      }
    } catch (e) {
      console.error('获取报表参数分类失败:', e);
    }

    return { variableFlags, filterFlags };
  };

  // 按 BKVision 工具规则拆分覆盖值到 constants / filters
  const splitOverrideParams = (
    override: Record<string, any>,
    variableFlags: Set<string>,
    filterFlags: Set<string>,
  ) => {
    const constants: Record<string, any> = {};
    const filters: Record<string, any> = {};

    Object.entries(override || {}).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') {
        return;
      }
      if (Array.isArray(value) && value.length === 0) {
        return;
      }

      // 与工具执行一致：明确是变量 → constants；明确是交互组件 → filters
      if (variableFlags.has(key)) {
        constants[key] = value;
      } else if (filterFlags.has(key)) {
        filters[key] = value;
      } else if (variableFlags.size === 0 && filterFlags.size === 0) {
        // 分类信息缺失时，默认按变量处理，避免 filters/constants 重复传参
        constants[key] = value;
      } else {
        // 有分类信息但未命中时，优先按交互组件（非 variable）处理
        filters[key] = value;
      }
    });

    return { constants, filters };
  };

  const clearPanelDom = () => {
    const panelEl = document.querySelector('#panel');
    if (panelEl) {
      panelEl.innerHTML = '';
    }
  };

  const destroyApp = () => {
    if (pendingInstance) {
      try {
        pendingInstance.unmount?.();
      } catch (e) {
        console.error(e);
      }
      pendingInstance = null;
    }
    if (app) {
      try {
        app.unmount();
      } catch (e) {
        console.error(e);
      }
      app = null;
    }
    // 并发 init 时 app 可能尚未赋值，必须清 DOM，否则图表会叠加两次
    clearPanelDom();
  };

  const init = async () => {
    if (!isValidId(route.params.id) || route.name !== 'statementManageDetail') {
      return;
    }

    const scopeConstants = getScopeConstants();
    const initKey = buildInitKey(scopeConstants);
    // 相同 panel + scope 且实例仍在，跳过重复初始化
    if (initKey === lastInitKey && app) {
      return;
    }

    initSeq += 1;
    const seq = initSeq;
    destroyApp();
    lastInitKey = '';

    try {
      if (!window.BkVisionSDK) {
        await loadScript(BKVISION_SCRIPT_SRC);
      }
      if (seq !== initSeq) return;

      // 覆盖配置失败不阻塞出图
      const panelDetail = await fetchPanelDetailWithOverride(scopeConstants);
      if (seq !== initSeq) return;

      const { variableFlags, filterFlags } = await resolveParamFlagSets(panelDetail.vision_id);
      if (seq !== initSeq) return;

      const { constants: overrideConstants, filters: overrideFilters } = splitOverrideParams(
        panelDetail.default_value_override,
        variableFlags,
        filterFlags,
      );

      // 再次确保容器干净，避免上一次异步渲染残留
      clearPanelDom();
      if (seq !== initSeq) return;

      const instance = await window.BkVisionSDK.init(
        '#panel',
        route.params.id,
        {
          apiPrefix: `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/bkvision/`,
          chartToolMenu: [
            { type: 'tool', id: 'fullscreen', build_in: true },
            { type: 'tool', id: 'refresh', build_in: true },
            { type: 'menu', id: 'excel', build_in: true },
          ],
          // 对齐 BKVision 工具：variable → constants，交互组件 → filters
          constants: {
            ...overrideConstants,
            ...scopeConstants,
          },
          filters: overrideFilters,
          handleError,
        },
      );
      pendingInstance = instance;
      if (seq !== initSeq) {
        instance?.unmount?.();
        if (pendingInstance === instance) {
          pendingInstance = null;
        }
        clearPanelDom();
        return;
      }
      app = instance;
      pendingInstance = null;
      lastInitKey = initKey;
    } catch (error) {
      if (seq === initSeq) {
        console.error(error);
        clearPanelDom();
      }
    }
  };

  // 不防抖：场景选择器会反复改 query，防抖会被不断重置导致永远不 init
  watch(
    () => [
      route.name,
      route.params.id,
      route.query.scene_id,
      route.query.scope_id,
      route.query.scope_type,
    ],
    () => {
      nextTick(() => {
        init();
      });
    },
    {
      immediate: true,
    },
  );

  onUnmounted(() => {
    initSeq += 1;
    lastInitKey = '';
    destroyApp();
  });

</script>
