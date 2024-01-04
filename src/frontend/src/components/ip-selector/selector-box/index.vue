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
  <bk-dialog
    class="ip-selector-dialog"
    :is-show="isShow"
    :title="t('选择目标')"
    width="1100">
    <bk-loading :loading="isTopoLoading">
      <div class="ip-selector-box">
        <div class="left-selector-box">
          <type-tab
            v-model="renderType"
            :uniqued-type="uniquedType" />
          <div class="operation-container">
            <component
              :is="renderComponent"
              v-if="!isTopoLoading"
              :biz-id="bizId"
              :last-host-list="resultHost"
              :last-node-list="resultNode"
              :last-service-template-list="resultServiceTemplate"
              :last-set-template-list="resultSetTemplate"
              :original-topo-tree-data="originalTopoTreeData"
              :topo-tree-data="topoTreeData"
              @change="handleValueChange" />
          </div>
        </div>
        <div class="left-preview-box">
          <preview-result
            :empty="isResultEmpty"
            :host-list="resultHost"
            :node-list="resultNode"
            :service-template-list="resultServiceTemplate"
            :set-template-list="resultSetTemplate"
            @change="handleValueChange" />
        </div>
      </div>
    </bk-loading>
    <template #footer>
      <bk-button
        class="mr8"
        theme="primary"
        @click="handleSubmit">
        {{ t('确定(OK)') }}
      </bk-button>
      <bk-button @click="handleCancle">
        {{ t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
    shallowRef,
    triggerRef,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BizManageService from '@service/biz-manage';

  import type HostInstanceStatusModel from '@model/biz/host-instance-status';
  import type NodeInstanceStatusModel from '@model/biz/node-instance-status';
  import type TemplateTopoModel from '@model/biz/template-topo';
  import type TopoModel from '@model/biz/topo';

  import useRequest from '@hooks/use-request';

  import PreviewResult from './components/preview-result/index.vue';
  import RenderCustomInput from './components/render-custom-input.vue';
  import RenderDynamicTopo from './components/render-dynamic-topo.vue';
  import RenderServiceTemplate from './components/render-service-template.vue';
  import RenderSetTemplate from './components/render-set-template.vue';
  import RenderStaticTopo from './components/render-static-topo.vue';
  import TypeTab from './components/type-tab.vue';
  import {
    mergeCustomInputHost,
    transformTopoToTree,
    type TTopoTreeData,
  } from './components/utils';

  interface Props {
    modelValue: Array<any>,
    type: string,
    bizId: number,
    isShow?: boolean,
    uniqued?: boolean
  }

  interface Emits {
    (e: 'change', value: { type: string, value: Array<any> }): void,
    (e: 'update:modelValue', value: { type: string, value: Array<any> }): void,
    (e: 'cancel'): void,
    (e: 'update:isShow', value: boolean): void,
  }

  const props = withDefaults(defineProps<Props>(), {
    isShow: false,
    uniqued: true,
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const tabTypeToNodeType = {
    dynamicTopo: 'TOPO',
    staticTopo: 'INSTANCE',
    serviceTemplate: 'SERVICE_TEMPLATE',
    setTemplate: 'SET_TEMPLATE',
    customInput: 'INSTANCE',
  };

  const nodeTypeToTabType = {
    TOPO: 'dynamicTopo',
    INSTANCE: 'staticTopo',
    SERVICE_TEMPLATE: 'serviceTemplate',
    SET_TEMPLATE: 'setTemplate',
  };

  const comMap = {
    dynamicTopo: RenderDynamicTopo,
    staticTopo: RenderStaticTopo,
    serviceTemplate: RenderServiceTemplate,
    setTemplate: RenderSetTemplate,
    customInput: RenderCustomInput,
  };

  const originalTopoTreeData = shallowRef<Array<TopoModel>>([]);
  const topoTreeData = shallowRef<Array<TTopoTreeData>>([]);
  const renderType = ref<keyof typeof comMap>('dynamicTopo');

  const resultHost = shallowRef<Array<HostInstanceStatusModel>>([]);
  const resultNode = shallowRef<Array<NodeInstanceStatusModel>>([]);
  const resultServiceTemplate = shallowRef<Array<TemplateTopoModel>>([]);
  const resultSetTemplate = shallowRef<Array<TemplateTopoModel>>([]);

  const renderComponent = computed(() => comMap[renderType.value]);
  const isResultEmpty = computed(() => resultHost.value.length < 1
    && resultNode.value.length < 1
    && resultServiceTemplate.value.length < 1
    && resultSetTemplate.value.length < 1);
  const uniquedType = computed(() => {
    if (!props.uniqued || isResultEmpty.value) {
      return '';
    }
    return tabTypeToNodeType[renderType.value];
  });

  const {
    loading: isTopoLoading,
    run: fetchTopoTree,
  } = useRequest(BizManageService.fetchTopoTree, {
    defaultValue: [],
    onSuccess(data) {
      originalTopoTreeData.value = data;
      topoTreeData.value = transformTopoToTree(data);
    },
  });
  // 显示 IP 选择器
  watch(() => props.isShow, (isShow) => {
    if (isShow) {
      fetchTopoTree({
        biz_id: props.bizId,
        instance_type: 'host',
        remove_empty_nodes: false,
      });
      renderType.value = 'dynamicTopo';
      if (props.type) {
        const newRenderType = nodeTypeToTabType[props.type as keyof typeof nodeTypeToTabType];
        if (newRenderType === 'dynamicTopo') {
          resultNode.value = [...props.modelValue];
        } else if (['staticTopo', 'customInput'].includes(newRenderType)) {
          resultHost.value = [...props.modelValue];
        } else if (newRenderType === 'serviceTemplate') {
          resultServiceTemplate.value = [...props.modelValue];
        } else if (newRenderType === 'setTemplate') {
          resultSetTemplate.value = [...props.modelValue];
        }
        renderType.value = newRenderType as keyof typeof tabTypeToNodeType;
      }
    }
  }, {
    immediate: true,
  });
  // tab 切换
  const handleValueChange = (type: keyof typeof comMap, value: Array<any>) => {
    if (type === 'dynamicTopo') {
      resultNode.value = value;
      triggerRef(resultNode);
    } else if (type === 'staticTopo') {
      resultHost.value = value;
      triggerRef(resultHost);
    } else if (type === 'serviceTemplate') {
      resultServiceTemplate.value = value;
      triggerRef(resultServiceTemplate);
    } else if (type === 'setTemplate') {
      resultSetTemplate.value = value;
      triggerRef(resultSetTemplate);
    } else if (type === 'customInput') {
      resultHost.value = mergeCustomInputHost(resultHost.value, value);
      triggerRef(resultHost);
    }
  };

  // 提交数据
  const handleSubmit = () => {
    let result: Array<any> = [];
    if (['staticTopo', 'customInput'].includes(renderType.value)) {
      result = resultHost.value;
    } else if (renderType.value === 'dynamicTopo') {
      result = resultNode.value;
    } else if (renderType.value === 'serviceTemplate') {
      result = resultServiceTemplate.value;
    } else if (renderType.value === 'setTemplate') {
      result = resultSetTemplate.value;
    }

    const value = {
      type: tabTypeToNodeType[renderType.value],
      value: result,
    };
    emits('change', value);
    emits('update:modelValue', value);
    emits('update:isShow', false);
  };

  // 取消
  const handleCancle = () => {
    resultHost.value = [];
    resultNode.value = [];
    resultServiceTemplate.value = [];
    resultSetTemplate.value = [];

    emits('cancel');
    emits('update:isShow', false);
  };
</script>
<style lang="postcss">
  .ip-selector-dialog {
    .bk-modal-footer {
      background: #fff !important;
      border-top: none !important;
    }

    .ip-selector-box {
      display: flex;
      min-height: 595px;
      border: 1px solid #dcdee5;
      border-radius: 2px 0 0;

      .left-selector-box {
        flex: 1 0 770px;

        .operation-container {
          padding: 16px;
        }
      }

      .left-preview-box {
        width: 280px;
        background: #f5f7fa;
        border-left: 1px solid #dcdee5;
      }

      table {
        .bk-checkbox {
          margin-right: 0;
        }

        tbody {
          .bk-checkbox {
            pointer-events: none;
          }
        }
      }
    }
  }

</style>
