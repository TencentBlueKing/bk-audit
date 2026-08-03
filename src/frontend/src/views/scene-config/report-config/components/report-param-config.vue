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
    v-if="inputVariable.length > 0"
    class="report-param-config">
    <div class="param-config-header">
      <div class="param-config-title">
        {{ t('参数配置') }}
      </div>
      <div class="param-config-desc">
        {{ t('设置仪表盘组件和变量的值，替代BKVision仪表盘的默认值') }}
      </div>
    </div>

    <!-- 交互组件 -->
    <div
      v-if="comList.length > 0"
      class="param-section">
      <div
        class="param-section-title"
        @click="isComCollapsed = !isComCollapsed">
        <audit-icon
          class="collapse-icon"
          :class="{ rotated: isComCollapsed }"
          type="angle-fill-down" />
        <span class="title-text">{{ t('交互组件') }}</span>
        <audit-icon
          v-bk-tooltips="comTipsOptions"
          class="info-fill"
          type="info-fill"
          @click.stop />
      </div>
      <div
        v-show="!isComCollapsed"
        class="param-list">
        <bk-vision-components
          v-for="comItem in comList"
          :key="comItem.raw_name"
          class="param-item"
          :config="comItem"
          :disabled="false"
          :info-box-class="INFO_BOX_CLASS"
          :report-lists-panels="reportListsPanels"
          @change="(val: any) => handleVisionChange(val, comItem.raw_name)"
          @change-is-default-value="(val: boolean) => handleIsDefaultValue(val, comItem.description)" />
      </div>
    </div>

    <!-- 变量 -->
    <div
      v-if="toolInfoVariable.length > 0"
      class="param-section">
      <div
        class="param-section-title"
        @click="isVarCollapsed = !isVarCollapsed">
        <audit-icon
          class="collapse-icon"
          :class="{ rotated: isVarCollapsed }"
          type="angle-fill-down" />
        <span class="title-text">{{ t('变量') }}</span>
        <audit-icon
          v-bk-tooltips="varTipsOptions"
          class="info-fill"
          type="info-fill"
          @click.stop />
      </div>
      <div
        v-show="!isVarCollapsed"
        class="param-list">
        <div
          v-for="(variables, variableIndex) in toolInfoVariable"
          :key="variables.raw_name"
          class="param-item">
          <div class="variables-title">
            <span
              v-bk-tooltips="{
                disabled: !variables.display_name,
                content: variables.display_name,
                placement: 'top',
                extCls: TIPS_EXT_CLS,
              }"
              class="variables-name">
              {{ variables.raw_name }}
            </span>
            <bk-checkbox
              class="title-right"
              :model-value="variables.is_default_value"
              size="small"
              @change="(checked: boolean | string | number) =>
                handleVariableDefaultValueToggle(checked === true, variableIndex)">
              {{ t('使用默认值') }}
            </bk-checkbox>
          </div>
          <bk-input
            :disabled="variables.is_default_value"
            :model-value="variables.default_value as string"
            placeholder=" "
            @update:model-value="(val: string) => handleVariableValueChange(variableIndex, val)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BkVisionComponents from '@views/tool-manage-shared/create-tool/components/bkvision/bk-vision-components.vue';

  export type ReportInputVariable = {
    raw_name: string;
    display_name: string;
    description: string;
    required: boolean;
    field_category: string;
    default_value: string | Array<string>;
    is_default_value: boolean;
    raw_default_value?: string | Array<string>;
    choices: Array<{ key: string; name: string }>;
  };

  interface Props {
    modelValue: ReportInputVariable[];
    reportListsPanels?: Array<Record<string, any>>;
  }

  interface Emits {
    (e: 'update:modelValue', value: ReportInputVariable[]): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    reportListsPanels: () => [],
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  /**
   * 侧滑 z-index=9999；v-bk-tooltips 不支持 zIndex，需 extCls + 全局样式抬升。
   * InfoBox 同样未透传 zIndex，用 class + CSS 处理。
   */
  const TIPS_EXT_CLS = 'report-param-config-tips';
  const INFO_BOX_CLASS = 'report-param-infobox-above-sideslider';

  const isComCollapsed = ref(false);
  const isVarCollapsed = ref(false);
  const comTipsOptions = computed(() => ({
    content: t('设置BKVision交互组件的默认值，用户打开图表后，可通过交互组件调整该值'),
    placement: 'top' as const,
    extCls: TIPS_EXT_CLS,
  }));
  const varTipsOptions = computed(() => ({
    content: t('设置BKVision变量的值，该值在图表打开后不可修改'),
    placement: 'top' as const,
    extCls: TIPS_EXT_CLS,
  }));

  const inputVariable = computed(() => props.modelValue || []);
  const comList = computed(() => inputVariable.value.filter(item => item.field_category !== 'variable'));
  const toolInfoVariable = computed(() => inputVariable.value.filter(item => item.field_category === 'variable'));

  const emitAll = (comItems: ReportInputVariable[], varItems: ReportInputVariable[]) => {
    emit('update:modelValue', [...comItems, ...varItems]);
  };

  const handleVisionChange = (value: any, rawName: string) => {
    const nextCom = comList.value.map(item => (item.raw_name === rawName
      ? { ...item, default_value: value }
      : item));
    emitAll(nextCom, toolInfoVariable.value);
  };

  const handleIsDefaultValue = (value: boolean, description: string) => {
    const nextCom = comList.value.map((item) => {
      if (item.description !== description) return item;
      if (value) {
        return {
          ...item,
          is_default_value: true,
          default_value: item.raw_default_value ?? item.default_value,
        };
      }
      return {
        ...item,
        is_default_value: false,
      };
    });
    emitAll(nextCom, toolInfoVariable.value);
  };

  const handleVariableDefaultValueToggle = (checked: boolean, index: number) => {
    if (checked) {
      InfoBox({
        class: INFO_BOX_CLASS,
        title: t('提示'),
        closeIcon: false,
        content: t('当启用「使用默认值」选项后，若在 BKVision 嵌入管理页面中对变量值进行修改，当前工具会有参数更新提示'),
        onConfirm() {
          const nextVars = toolInfoVariable.value.map((item, i) => {
            if (i !== index) return item;
            return {
              ...item,
              is_default_value: true,
              default_value: item.raw_default_value || '',
            };
          });
          emitAll(comList.value, nextVars);
        },
      });
      return;
    }
    const nextVars = toolInfoVariable.value.map((item, i) => (i === index
      ? { ...item, is_default_value: false }
      : item));
    emitAll(comList.value, nextVars);
  };

  const handleVariableValueChange = (index: number, val: string) => {
    const nextVars = toolInfoVariable.value.map((item, i) => (i === index
      ? { ...item, default_value: val }
      : item));
    emitAll(comList.value, nextVars);
  };
</script>

<style lang="postcss" scoped>
/* 对齐侧滑表单：标签 12px、区块间距与 bk-form-item 接近 */
.report-param-config {
  margin-bottom: 20px;
}

.param-config-header {
  margin-bottom: 8px;
}

.param-config-title {
  font-size: 12px;
  line-height: 20px;
  color: #63656e;
}

.param-config-desc {
  margin-top: 2px;
  font-size: 12px;
  line-height: 18px;
  color: #979ba5;
}

.param-section {
  margin-top: 8px;

  & + .param-section {
    margin-top: 12px;
  }
}

.param-section-title {
  display: flex;
  align-items: center;
  height: 22px;
  cursor: pointer;
  user-select: none;
}

.collapse-icon {
  flex-shrink: 0;
  font-size: 12px;
  color: #979ba5;
  transition: transform .2s ease;
}

.rotated {
  display: inline-block;
  transform: rotate(-90deg);
}

.title-text {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 700;
  line-height: 20px;
  color: #4d4f56;
}

.info-fill {
  margin-left: 4px;
  font-size: 14px;
  color: #a3c5fd;
  cursor: pointer;
}

.param-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}

.param-item {
  width: 100%;
}

.variables-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  font-size: 12px;
  line-height: 20px;
  color: #63656e;

  .variables-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .title-right {
    flex-shrink: 0;
    color: #3a84ff;
  }
}

:deep(.bk-vision-component .component .lable) {
  gap: 12px;
  margin-bottom: 2px;
  padding-bottom: 0;
  font-size: 12px;
  color: #63656e;
}
</style>

<!-- 挂到 body 的 tips / InfoBox，需非 scoped 抬升至侧滑之上 -->
<style lang="postcss">
.bk-popper.report-param-config-tips {
  z-index: 10060 !important;
}

.bk-infobox.report-param-infobox-above-sideslider,
.bk-infobox.report-param-infobox-above-sideslider .bk-modal-wrapper,
.bk-infobox.report-param-infobox-above-sideslider .bk-modal-mask {
  z-index: 10060 !important;
}
</style>
