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
    class="form-search-item"
    :class="attrs.class">
    <div class="search-item-lable">
      {{ t(config.label) }}
      <span
        v-if="config.required"
        style="color: #ea3636;">*</span>
      <span :id="`${name}ItemLabelAppend`" />
      <template v-if="config.help">
        <bk-popover
          :component-event-delay="300"
          placement="top"
          theme="light">
          <audit-icon
            style="color: #c4c6cc; cursor: pointer;"
            type="help-fill" />
          <template #content>
            <div id="pop_content">
              {{ t('模糊匹配') }},
              <a
                :href="configData.third_doc_url.search_rule_iwiki_url"
                target="_blank"> {{ t('查看规则详情') }}</a>
            </div>
          </template>
        </bk-popover>
      </template>
      <audit-icon
        v-if="config.canClose"
        class="search-item-lable-close"
        type="close"
        @click="deleteField" />
    </div>
    <component
      :is="renderCom"
      ref="formItem"
      :config="config"
      :default-value="model[name]"
      :model="model"
      :name="name"
      v-bind="{ ...inhertProps, ...listeners }" />
  </div>
</template>
<script lang="ts">
  export default {
    inheritAttrs: false,
  };
</script>
<script setup lang="ts">
  import {
    computed,
    ref,
    useAttrs,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useListeners from '@hooks/use-listeners';
  import useProps from '@hooks/use-props';

  import type { IFieldConfig } from './config';
  import RenderActionId from './strategy/action-id.vue';
  import RenderCascader from './strategy/cascader.vue';
  import RenderDatetimerang from './strategy/datetimerange.vue';
  import RenderExpr from './strategy/expr.vue';
  import RenderInput from './strategy/input.vue';
  import RenderResourceTypeId from './strategy/resource-type-id.vue';
  import RenderSelect from './strategy/select.vue';
  import RenderSensitive from './strategy/sensitive.vue';
  import RenderSystemId from './strategy/system-id.vue';
  import RenderUserSelector from './strategy/user-selector.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    name: string,
    model: Record<string, any>
    baseConfig: Record<string, IFieldConfig>
  }
  interface Exposes {
    getValue: (fieldValue?: string)=> Promise<Record<string, any>|string>
  }
  interface Emit {
    (e: 'deleteField', value: keyof typeof props.baseConfig): void
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emit>();
  const { t } = useI18n();

  const attrs = useAttrs();
  const inhertProps = useProps();
  const listeners = useListeners();

  const config = props.baseConfig[props.name as keyof typeof props.baseConfig];

  const comMap = {
    'action-id': RenderActionId,
    datetimerange: RenderDatetimerang,
    expr: RenderExpr,
    string: RenderInput,
    'resource-type-id': RenderResourceTypeId,
    select: RenderSelect,
    sensitive: RenderSensitive,
    'system-id': RenderSystemId,
    'user-selector-tenant': RenderUserSelector,
    cascader: RenderCascader,
  };

  const renderCom = computed(() => comMap[config.type as keyof typeof comMap]);
  const formItem = ref();

  const deleteField = () => {
    emit('deleteField', props.name);
  };

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  defineExpose<Exposes>({
    getValue(fieldValue?: string) {
      return formItem.value.getValue(fieldValue);
    },
  });
</script>
<style lang="postcss">
  .form-search-item {
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    vertical-align: top;

    .search-item-lable {
      margin-bottom: 6px;

      .search-item-lable-close {
        display: none;
        float: right;
        line-height: 20px;
        cursor: pointer;
      }

      &:hover {
        .search-item-lable-close {
          display: block;
        }
      }
    }

    .bk-select {
      &.is-selected-all {
        .bk-tag-close {
          display: none !important;
        }
      }
    }
  }

  .analysis-mult-select-action {
    display: flex;
    width: 100%;
    color: #63656e;

    .action-item {
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 1;
      height: 32px;

      & ~ & {
        border-left: 1px solid #dcdee5;
      }

      &:hover {
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }
</style>
