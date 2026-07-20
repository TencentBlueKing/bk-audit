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
  <div
    :id="`panel-${props.uid}`"
    ref="panelRef"
    class="panel" />
</template>

<script setup lang="ts">
  import { onUnmounted, ref } from 'vue';

  import ToolManageService from '@service/tool-manage';

  import IamApplyDataModel from '@model/iam/apply-data';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useMessage from '@hooks/use-message';

  import useEventBus from '@/hooks/use-event-bus';
  import useRequest from '@/hooks/use-request';

  interface DrillDownItem {
    raw_name: string;
    display_name: string;
    description: string;
    drill_config: Array<{
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
        target_field_type?: string;
      }>;
      drill_name?: string;
    }>;
  }

  interface SearchItem {
    value: any;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
  }

  interface Props {
    uid: string;
    toolDetails: ToolDetailModel;
    isDrillDownOpen: boolean;
    drillDownItemConfig: DrillDownItem['drill_config'][0]['config'];
    drillDownItemRowData: Record<string, any>;
    searchList: SearchItem[];
    riskToolParams?: Record<string, any>;
  }

  interface Error {
    data: Record<string, any>,
    message: string,
    status: number
  }

  const props = withDefaults(defineProps<Props>(), {
    riskToolParams: () => ({}),
  });

  const emit = defineEmits<{
    executed: [];
  }>();

  let app: any;

  const panelRef = ref<HTMLElement | null>(null);
  const panelId = ref('');
  const isExecuting = ref(false);
  const { messageError } = useMessage();
  const emitBus = useEventBus().emit;

  // 获取工具执行结果
  const {
    run: fetchToolsExecute,
  } = useRequest(ToolManageService.fetchToolsExecute, {
    defaultValue: {},
    onSuccess: (data) => {
      if (data?.data?.panel_id) {
        panelId.value = data.data.panel_id;
        initBK(panelId.value);
      }
      emit('executed');
    },
    onFinally: () => {
      isExecuting.value = false;
    },
  });

  // 执行工具（使用 toolDetails.uid 作为真实工具uid来调用后端API）
  const executeTool = () => {
    if (isExecuting.value) return;
    isExecuting.value = true;
    fetchToolsExecute({
      uid: props.toolDetails?.uid || props.uid,
      params: {
        tool_variables: props.searchList.map(item => ({
          raw_name: item.raw_name,
          // eslint-disable-next-line no-nested-ternary
          value: (item.field_category === 'person_select') ? (item.value.length === 0 ?  '' :  item.value.join(','))  :  item.value        })),
      },
      ...(props.riskToolParams && Object.keys(props.riskToolParams).length > 0 ? props.riskToolParams : {}),
    });
  };

  const TOOLTIP_WRAP_STYLE_ID = 'audit-bkvision-tooltip-wrap';
  const TOOLTIP_WRAP_CSS = `
    /* OverflowTitle tips 默认 boundary=document.body，BKVision scopeCss 后 max-width/换行会失效 */
    .bk-popover,
    .bk-pop2-content,
    .t-popup__content:not(:has(.t-select__dropdown)):not(:has(.t-list)):not(:has(.t-menu)):not(:has(.t-tree)),
    .t-popup__content .text-ov,
    .t-popup .text-ov,
    [class*='overflow-popover']:not(.overflow-popover-reference) {
      max-width: min(480px, 80vw) !important;
      white-space: normal !important;
      word-break: break-all !important;
      overflow-wrap: anywhere !important;
      line-height: 1.4;
    }
  `;

  const injectTooltipWrapStyle = (root: ParentNode | ShadowRoot | null | undefined) => {
    if (!root) {
      return;
    }
    const existed = 'getElementById' in root
      ? (root as Document | ShadowRoot).getElementById(TOOLTIP_WRAP_STYLE_ID)
      : (root as ParentNode).querySelector?.(`#${TOOLTIP_WRAP_STYLE_ID}`);
    if (existed) {
      return;
    }
    const style = document.createElement('style');
    style.id = TOOLTIP_WRAP_STYLE_ID;
    style.textContent = TOOLTIP_WRAP_CSS;
    root.appendChild(style);
  };

  // 关闭弹窗时清理实例
  const closeBK = () => {
    if (app) {
      app.unmount();
      app = null;
    }
  };

  // 加载脚本
  const loadScript = (src: string) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve(script);
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
    document.head.appendChild(script);
  });

  // 错误处理
  const handleError = (_type: 'dashboard' | 'chart' | 'action' | 'others', err: Error) => {
    if (err.data.code === '9900403') {
      const iamResult = new IamApplyDataModel(err.data.data || {});
      // 页面展示没权限提示
      emitBus('permission-page', iamResult);
    } else {
      messageError(err.message);
    }
  };

  // 初始化 BKVision
  const initBK = async (id: string) => {
    if (app) {
      app.unmount();
      app = null;
    }
    if (panelRef.value) {
      panelRef.value.innerHTML = '';
    }

    const filters: Record<string, any> = {};
    const drillDownFilters: Record<string, any> = {};
    const constants: Record<string, any> = {};

    // 初始化将默认值添加到常量中
    props.toolDetails?.config.input_variable.forEach((item: any) => {
      if (item.default_value && (Array.isArray(item.default_value) ? item.default_value.length > 0 : true)) {
        if (item.field_category === 'variable') {
          constants[item.raw_name] = item.default_value || '';
        } else {
          filters[item.raw_name] = item.default_value;
        }
      } else if (item.field_category === 'variable') {
        constants[item.raw_name] = '';
      }
    });

    // URL 传参 / 用户输入优先覆盖默认值
    props.searchList?.forEach((item) => {
      const hasValue = item.value !== null && item.value !== undefined && item.value !== ''
        && (!Array.isArray(item.value) || item.value.length > 0);
      if (!hasValue) return;
      if (item.field_category === 'variable') {
        constants[item.raw_name] = item.value;
      } else {
        filters[item.raw_name] = item.value;
      }
    });

    // 将风险工具参数添加到常量中
    if (props.riskToolParams && Object.keys(props.riskToolParams).length > 0) {
      Object.keys(props.riskToolParams).forEach((key) => {
        if (props.riskToolParams && key in props.riskToolParams) {
          constants[key] = props.riskToolParams[key];
        } else {
          constants[key] = '';
        }
      });
    }

    // 下钻 常量使用下钻的值
    if (props.isDrillDownOpen) {
      props.drillDownItemConfig.forEach((item) => {
        // 根据源字段名称查找对应的字段分类
        const fieldCategory = props.toolDetails?.config.input_variable
          .find((i: any) => i.raw_name === item.source_field)?.field_category;

        if (item.target_value_type === 'field') { // 目标值为字段引用类型
          if (item.target_field_type === 'basic' || !item.target_field_type) {
            // 从根对象中获取字段值
            if (fieldCategory === 'variable') {
              // 变量类型字段：存储到 constants 中，用于工具执行时的参数传递
              constants[item.source_field] = props.drillDownItemRowData?.[item.target_value] ?? '';
            } else {
              // 过滤器类型字段：存储到 drillDownFilters 中，用于数据过滤
              drillDownFilters[item.source_field] = props.drillDownItemRowData?.[item.target_value] ?? '';
            }
          } else {
            // 从 event_data 嵌套对象中获取字段值
            if (fieldCategory === 'variable') {
              // 变量类型字段：存储到 constants 中
              constants[item.source_field] = props.drillDownItemRowData?.event_data?.[item.target_value] ?? '';
            } else {
              // 过滤器类型字段：存储到 drillDownFilters 中
              drillDownFilters[item.source_field] = props.drillDownItemRowData?.event_data?.[item.target_value] ?? '';
            }
          }
        } else { // 目标值为固定值类型
          if (fieldCategory === 'variable') {
            // 变量类型字段：直接使用固定值，存储到 constants 中
            constants[item.source_field] = item.target_value || '';
          } else {
            // 过滤器类型字段：直接使用固定值，存储到 drillDownFilters 中
            drillDownFilters[item.source_field] = item.target_value;
          }
        }
      });
    }

    try {
      if (!window.BkVisionSDK) {
        await loadScript('https://staticfile.qq.com/bkvision/pbb9b207ba200407982a9bd3d3f2895d4/latest/main.js');
      }
      app = await window.BkVisionSDK.init(
        `#panel-${props.uid}`,
        id,
        {
          apiPrefix: `${window.PROJECT_CONFIG.AJAX_URL_PREFIX}/bkvision/`,
          chartToolMenu: [
            { type: 'tool', id: 'fullscreen', build_in: true },
            { type: 'tool', id: 'refresh', build_in: true },
            { type: 'menu', id: 'excel', build_in: true },
          ],
          filters: props.isDrillDownOpen ? drillDownFilters : filters,
          constants,
          handleError,
        },
      );
      // BKVision 运行在 Shadow DOM，且气泡可能 teleport 到 body；两边都注入换行样式
      injectTooltipWrapStyle(document.head);
      const visionPanel = panelRef.value?.querySelector('bk-vision-panel') as HTMLElement & {
        shadowRoot?: ShadowRoot | null;
      } | null;
      injectTooltipWrapStyle(visionPanel?.shadowRoot);
    } catch (error) {
      console.error(error);
    }
  };
  defineExpose({
    executeTool,
    panelRef,
    closeBK,
  });

  // 组件销毁时清理实例（作为后备机制）
  onUnmounted(() => {
    if (app) {
      app.unmount();
      app = null;
    }
  });
</script>

<style scoped lang="postcss">
.panel {
  width: 100%;
  height: 100%;
}
</style>

<!--
  BKVision 表格 OverflowTitle tips 会挂到 document.body，scopeCss 后自身换行样式失效。
  这里用非 scoped 样式兜底（与 init 注入逻辑一致）。
-->
<style lang="postcss">
.bk-popover,
.bk-pop2-content,
.t-popup__content:not(:has(.t-select__dropdown), :has(.t-list), :has(.t-menu), :has(.t-tree)),
.t-popup__content .text-ov,
.t-popup .text-ov,
[class*='overflow-popover']:not(.overflow-popover-reference) {
  max-width: min(480px, 80vw) !important;
  line-height: 1.4;
  word-break: break-all !important;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
}
</style>
