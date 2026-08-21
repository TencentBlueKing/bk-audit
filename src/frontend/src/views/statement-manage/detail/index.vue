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
  <!-- 普通报表：沿用原有 100% 容器 -->
  <div
    v-if="!isLargeScreenReport"
    class="statement-detail-normal">
    <div
      id="panel"
      ref="panelRef" />
  </div>
  <!-- 指定大屏报表：Teleport + 等比缩放 + 可滚动 -->
  <template v-else>
    <div class="statement-detail-placeholder" />
    <teleport to="body">
      <div
        ref="wrapRef"
        class="statement-detail">
        <div
          ref="scalerRef"
          class="statement-detail__scaler">
          <div
            id="panel"
            ref="panelRef"
            class="statement-detail__panel" />
        </div>
      </div>
    </teleport>
  </template>
</template>
<script setup lang="ts">
  import {
    computed,
    nextTick,
    onDeactivated,
    onMounted,
    onUnmounted,
    ref,
    watch,
  } from 'vue';
  import {
    onBeforeRouteLeave,
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

  // 仅这些报表走大屏适配；其余保持原来的普通嵌入方式
  const LARGE_SCREEN_PANEL_IDS = new Set([
    '555a9e45d36a3029afbde612e4dbe7ff',
  ]);

  const BKVISION_SCRIPT_SRC = 'https://staticfile.qq.com/bkvision/pbb9b207ba200407982a9bd3d3f2895d4/latest/main.js';
  const FALLBACK_WIDTH = 1920;
  const FALLBACK_HEIGHT = 1080;
  const TOP_NAV_HEIGHT = 52;

  const route = useRoute();
  const wrapRef = ref<HTMLElement | null>(null);
  const scalerRef = ref<HTMLElement | null>(null);
  const panelRef = ref<HTMLElement | null>(null);
  const { messageError } = useMessage();
  const {  emit } = useEventBus();
  let app: any;
  let initSeq = 0;
  let lastInitKey = '';
  let pendingInstance: any = null;
  let canvasW = FALLBACK_WIDTH;
  let canvasH = FALLBACK_HEIGHT;
  let canvasLocked = false;
  let contentObserver: MutationObserver | null = null;
  let remountTimers: number[] = [];
  let layoutRaf = 0;
  let sideResizeObserver: ResizeObserver | null = null;

  const isLargeScreenReport = computed(() => (
    LARGE_SCREEN_PANEL_IDS.has(String(route.params.id || ''))
  ));

  const isValidId = (id: any): boolean => {
    if (!id) return false;
    if (id === 'undefined' || id === 'null') return false;
    if (typeof id === 'string' && id.trim() === '') return false;
    return true;
  };

  const isActiveOnDetailRoute = () => (
    route.name === 'statementManageDetail' && isValidId(route.params.id)
  );

  const parsePx = (value: string) => {
    const num = parseFloat(value);
    return Number.isFinite(num) ? num : 0;
  };

  const isSaneSize = (w: number, h: number) => (
    w >= 400 && w <= 4000 && h >= 300 && h <= 2500
  );

  /** 穿透 shadow，量 vue-grid-item 真实包围盒（不要用 1920×1080 空高，否则会「浮」在中间） */
  const measureVisionCanvas = (): { w: number, h: number } | null => {
    const panel = panelRef.value;
    if (!panel) return null;

    const roots: ParentNode[] = [panel];
    const queue: Element[] = [panel];
    while (queue.length) {
      const el = queue.shift()!;
      if (el.shadowRoot) {
        roots.push(el.shadowRoot);
        queue.push(...Array.from(el.shadowRoot.children));
      }
      queue.push(...Array.from(el.children));
    }

    for (const root of roots) {
      const items = root.querySelectorAll?.('.vue-grid-item');
      if (!items?.length) continue;
      let maxRight = 0;
      let maxBottom = 0;
      items.forEach((node) => {
        const item = node as HTMLElement;
        const left = parsePx(item.style.left) || item.offsetLeft;
        const top = parsePx(item.style.top) || item.offsetTop;
        const width = parsePx(item.style.width) || item.offsetWidth;
        const height = parsePx(item.style.height) || item.offsetHeight;
        maxRight = Math.max(maxRight, left + width);
        maxBottom = Math.max(maxBottom, top + height);
      });
      const w = Math.ceil(maxRight);
      const h = Math.ceil(maxBottom);
      if (isSaneSize(w, h)) return { w, h };
    }
    return null;
  };

  /**
   * 侧栏右、标题栏下：保留 page-title；宽度等比适配，高度超出可滚动。
   * 顶部预留工具条空间，避免全屏/刷新按钮被裁切。
   */
  const updatePanelLayout = () => {
    if (!isActiveOnDetailRoute() || !isLargeScreenReport.value) return;
    const wrap = wrapRef.value;
    const scaler = scalerRef.value;
    const panel = panelRef.value;
    if (!wrap || !scaler || !panel) return;

    const sideEl = document.querySelector('.audit-navigation-side') as HTMLElement | null;
    const titleEl = document.querySelector('.audit-navigation-main .page-title') as HTMLElement | null;
    // 若上次隐藏过标题，这里强制恢复
    if (titleEl) {
      titleEl.style.display = '';
    }

    const sideRect = sideEl?.getBoundingClientRect();
    const titleRect = titleEl?.getBoundingClientRect();
    const left = sideRect
      ? Math.ceil(sideRect.right)
      : 220;
    // 必须在标题栏下方，标题保持显示
    const top = titleRect
      ? Math.ceil(titleRect.bottom)
      : (TOP_NAV_HEIGHT + 52);
    const cw = Math.max(window.innerWidth - left, 0);
    const ch = Math.max(window.innerHeight - top, 0);
    if (!cw || !ch) return;

    // BKVision 顶部工具按钮大约需要 40px，避免贴顶被 overflow 裁掉
    const toolBarGap = 40;

    wrap.style.cssText = [
      'position:fixed',
      `top:${top}px`,
      `left:${left}px`,
      `width:${cw}px`,
      `height:${ch}px`,
      'z-index:100',
      'margin:0',
      `padding:${toolBarGap}px 0 0`,
      'overflow:auto',
      'background:transparent',
      'display:block',
      'box-sizing:border-box',
    ].join(';');

    // 先清缩放再量
    panel.style.cssText = 'position:absolute;top:0;left:0;transform:none;margin:0;padding:0;';

    if (!canvasLocked) {
      const measured = measureVisionCanvas();
      if (measured) {
        canvasW = measured.w;
        canvasH = measured.h;
        canvasLocked = true;
      }
    }

    // 可用宽度需扣除纵向滚动条，减少横向溢出
    const scrollBarW = wrap.offsetWidth - wrap.clientWidth;
    const fitW = Math.max(cw - scrollBarW, 0) || cw;
    const scale = fitW / canvasW;
    const scaledW = Math.ceil(canvasW * scale);
    const scaledH = Math.ceil(canvasH * scale);

    scaler.style.cssText = [
      'position:relative',
      `width:${scaledW}px`,
      `height:${scaledH}px`,
      'margin:0',
      'padding:0',
    ].join(';');

    panel.style.cssText = [
      'position:absolute',
      'top:0',
      'left:0',
      `width:${canvasW}px`,
      `height:${canvasH}px`,
      `transform:scale(${scale})`,
      'transform-origin:left top',
      'margin:0',
      'padding:0',
      'will-change:transform',
      'background:transparent',
    ].join(';');
  };

  const scheduleLayout = () => {
    if (layoutRaf) cancelAnimationFrame(layoutRaf);
    layoutRaf = requestAnimationFrame(() => {
      layoutRaf = 0;
      updatePanelLayout();
    });
  };

  const clearRemountTimers = () => {
    remountTimers.forEach(id => window.clearTimeout(id));
    remountTimers = [];
  };

  const stopContentObserver = () => {
    contentObserver?.disconnect();
    contentObserver = null;
    clearRemountTimers();
    if (layoutRaf) {
      cancelAnimationFrame(layoutRaf);
      layoutRaf = 0;
    }
  };

  const watchVisionContent = () => {
    if (!isLargeScreenReport.value) return;
    stopContentObserver();
    const panel = panelRef.value;
    if (!panel) return;

    contentObserver = new MutationObserver(() => {
      // 图表尚未量到真实尺寸时允许重测
      if (!canvasLocked) scheduleLayout();
    });
    contentObserver.observe(panel, { childList: true, subtree: true });

    // shadow 晚挂载：延迟探测并锁定画布尺寸
    const delays = [0, 100, 300, 600, 1200, 2500, 4000];
    delays.forEach((ms) => {
      const id = window.setTimeout(() => {
        if (!isActiveOnDetailRoute()) return;
        const host = panel.querySelector('*');
        if (host?.shadowRoot && contentObserver) {
          contentObserver.observe(host.shadowRoot, { childList: true, subtree: true });
        }
        if (!canvasLocked) {
          updatePanelLayout();
        }
      }, ms);
      remountTimers.push(id);
    });
  };

  const resetWrapLayout = () => {
    stopContentObserver();
    const titleEl = document.querySelector('.audit-navigation-main .page-title') as HTMLElement | null;
    if (titleEl) {
      titleEl.style.display = '';
    }
    const wrap = wrapRef.value;
    if (wrap) {
      wrap.style.cssText = 'display:none';
    }
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
    if (!isActiveOnDetailRoute()) return;
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
    const panelEl = panelRef.value || document.querySelector('#panel');
    if (panelEl) {
      panelEl.innerHTML = '';
    }
  };

  const abortInit = () => {
    initSeq += 1;
    lastInitKey = '';
    canvasLocked = false;
    canvasW = FALLBACK_WIDTH;
    canvasH = FALLBACK_HEIGHT;
    destroyApp();
    resetWrapLayout();
  };

  const destroyApp = () => {
    stopContentObserver();
    canvasLocked = false;
    canvasW = FALLBACK_WIDTH;
    canvasH = FALLBACK_HEIGHT;
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
    if (!isActiveOnDetailRoute()) {
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
    if (isLargeScreenReport.value) {
      updatePanelLayout();
    } else {
      resetWrapLayout();
    }

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
      // 切换普通/大屏时 DOM 结构不同，等下一帧再挂载
      await nextTick();
      if (isLargeScreenReport.value) {
        updatePanelLayout();
      }
      if (seq !== initSeq || !isActiveOnDetailRoute()) return;
      if (!panelRef.value && !document.querySelector('#panel')) return;

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
      if (seq !== initSeq || !isActiveOnDetailRoute()) {
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
      nextTick(() => {
        if (isLargeScreenReport.value) {
          updatePanelLayout();
          watchVisionContent();
        }
      });
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
        if (!isActiveOnDetailRoute()) {
          abortInit();
          return;
        }
        init();
      });
    },
    {
      immediate: true,
    },
  );

  onBeforeRouteLeave(() => {
    abortInit();
  });

  onDeactivated(() => {
    abortInit();
  });

  const handleResizeOrSideChange = () => {
    if (isLargeScreenReport.value) {
      scheduleLayout();
    }
  };

  onMounted(() => {
    window.addEventListener('resize', handleResizeOrSideChange);
    const sideEl = document.querySelector('.audit-navigation-side');
    if (sideEl && typeof ResizeObserver !== 'undefined') {
      sideResizeObserver = new ResizeObserver(handleResizeOrSideChange);
      sideResizeObserver.observe(sideEl);
    }
    if (isLargeScreenReport.value) {
      nextTick(() => {
        updatePanelLayout();
        requestAnimationFrame(() => updatePanelLayout());
      });
    }
  });

  onUnmounted(() => {
    window.removeEventListener('resize', handleResizeOrSideChange);
    sideResizeObserver?.disconnect();
    sideResizeObserver = null;
    abortInit();
  });

</script>
<style lang="postcss" scoped>
.statement-detail-normal {
  width: 100%;
  height: 100%;
}

.statement-detail-placeholder {
  width: 100%;
  height: calc(100vh - 104px);
}

.statement-detail {
  box-sizing: border-box;
}

.statement-detail__scaler {
  position: relative;
}

.statement-detail__panel {
  position: absolute;
  top: 0;
  left: 0;
}
</style>
