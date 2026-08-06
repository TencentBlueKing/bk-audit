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
  <div class="bkvision-param-config">
    <div class="param-card-title">
      {{ t('参数配置') }}
    </div>
    <div class="param-card-body">
      <bk-exception
        v-if="!hasReport"
        scene="part"
        type="empty">
        {{ t('请先选择BKVision报表') }}
      </bk-exception>

      <bk-exception
        v-else-if="hasNoParam"
        scene="part"
        type="empty">
        {{ t('当前报表暂无参数配置') }}
      </bk-exception>

      <div v-else>
        <!-- 交互组件 -->
        <div
          v-if="comList.length > 0"
          class="param-section">
          <div
            class="section-header"
            @click="isComExpanded = !isComExpanded">
            <audit-icon
              class="section-arrow"
              :class="{ 'is-collapsed': !isComExpanded }"
              type="angle-fill-down" />
            <span class="title-text">{{ t('交互组件') }}</span>
            <img
              class="title-info-icon"
              src="@/images/info-gray.svg">
            <span class="title-desc">
              {{ t('设置BKVision交互组件的默认值，用户打开图表后，可通过交互组件调整该值') }}
            </span>
          </div>
          <div
            v-show="isComExpanded"
            class="param-list">
            <div
              v-for="item in comList"
              :key="item.raw_name"
              class="param-item">
              <div class="param-label">
                <span
                  v-bk-tooltips="{
                    disabled: getPanelTooltip(item) === '',
                    content: getPanelTooltip(item)
                  }">{{ item.display_name }}({{ item.raw_name }})</span>
                <bk-popover
                  :is-show="defaultTipVisibleMap[item.raw_name] === true"
                  placement="top"
                  theme="light"
                  trigger="manual"
                  :z-index="10050"
                  @after-hidden="hideDefaultTip(item.raw_name)">
                  <bk-checkbox
                    class="title-right is-black-text"
                    :disabled="false"
                    :model-value="item.is_default_value"
                    size="small"
                    @change="checked => handleDefaultValueToggle(checked, item)">
                    {{ t('使用默认值') }}
                  </bk-checkbox>
                  <template #content>
                    <div class="default-value-tip-popover">
                      <div class="default-value-tip-text">
                        {{ t('勾选后，若在 BKVision 嵌入管理页面中对变量值进行修改，当前工具会有参数更新提示') }}
                      </div>
                      <div class="default-value-tip-actions">
                        <bk-button
                          size="small"
                          theme="primary"
                          @click="handleConfirmDefaultTip(item)">
                          {{ t('知道了') }}
                        </bk-button>
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>

              <div class="param-content">
                <bk-date-picker
                  v-if="item.field_category === 'time-picker'"
                  append-to-body
                  :disabled="item.is_default_value"
                  format="yyyy-MM-dd HH:mm:ss"
                  :model-value="getDateValue(item)"
                  :shortcuts="dateShortCut"
                  type="datetime"
                  use-shortcut-text
                  @change="val => updateItemDefaultValue(val, item)" />
                <div
                  v-else-if="item.field_category === 'time-ranger'"
                  class="range-wrapper"
                  @mouseenter="hoverDeleteKey = item.raw_name"
                  @mouseleave="hoverDeleteKey = ''">
                  <date-picker
                    :disabled="item.is_default_value"
                    :model-value="getRangeValue(item)"
                    style="width: 100%;"
                    @update:model-value="(val: string[]) => updateItemDefaultValue(val, item)" />
                  <audit-icon
                    v-if="hoverDeleteKey === item.raw_name && !item.is_default_value"
                    class="delete"
                    type="delete-fill"
                    @click="updateItemDefaultValue([], item)" />
                </div>
                <bk-input
                  v-else-if="item.field_category === 'inputer'"
                  :disabled="item.is_default_value"
                  :model-value="typeof item.default_value === 'string' ? item.default_value : ''"
                  @change="val => updateItemDefaultValue(val, item)" />
                <bk-tag-input
                  v-else
                  allow-create
                  collapse-tags
                  :disabled="item.is_default_value"
                  has-delete-icon
                  :list="[]"
                  :model-value="getTagValue(item)"
                  @change="val => updateItemDefaultValue(val, item)" />
              </div>
            </div>
          </div>
        </div>

        <!-- 变量 -->
        <div
          v-if="variableList.length > 0"
          class="param-section">
          <div
            class="section-header"
            @click="isVarExpanded = !isVarExpanded">
            <audit-icon
              class="section-arrow"
              :class="{ 'is-collapsed': !isVarExpanded }"
              type="angle-fill-down" />
            <span class="title-text">{{ t('变量') }}</span>
            <img
              class="title-info-icon"
              src="@/images/info-gray.svg">
            <span class="title-desc">
              {{ t('设置BKVision变量的值，该值在图表打开后不可修改') }}
            </span>
          </div>
          <div
            v-show="isVarExpanded"
            class="param-list">
            <div
              v-for="item in variableList"
              :key="item.raw_name"
              class="param-item">
              <div class="param-label">
                <span>{{ item.display_name }}({{ item.raw_name }})</span>
                <bk-popover
                  :is-show="defaultTipVisibleMap[item.raw_name] === true"
                  placement="top"
                  theme="light"
                  trigger="manual"
                  :z-index="10050"
                  @after-hidden="hideDefaultTip(item.raw_name)">
                  <bk-checkbox
                    class="title-right is-black-text"
                    :disabled="false"
                    :model-value="item.is_default_value"
                    size="small"
                    @change="checked => handleDefaultValueToggle(checked, item)">
                    {{ t('使用默认值') }}
                  </bk-checkbox>
                  <template #content>
                    <div class="default-value-tip-popover">
                      <div class="default-value-tip-text">
                        {{ t('勾选后，若在 BKVision 嵌入管理页面中对变量值进行修改，当前工具会有参数更新提示') }}
                      </div>
                      <div class="default-value-tip-actions">
                        <bk-button
                          size="small"
                          theme="primary"
                          @click="handleConfirmDefaultTip(item)">
                          {{ t('知道了') }}
                        </bk-button>
                      </div>
                    </div>
                  </template>
                </bk-popover>
              </div>

              <div class="param-content">
                <bk-date-picker
                  v-if="item.field_category === 'time-picker'"
                  append-to-body
                  :disabled="item.is_default_value"
                  format="yyyy-MM-dd HH:mm:ss"
                  :model-value="getDateValue(item)"
                  :shortcuts="dateShortCut"
                  type="datetime"
                  use-shortcut-text
                  @change="val => updateItemDefaultValue(val, item)" />
                <div
                  v-else-if="item.field_category === 'time-ranger'"
                  class="range-wrapper"
                  @mouseenter="hoverDeleteKey = item.raw_name"
                  @mouseleave="hoverDeleteKey = ''">
                  <date-picker
                    :disabled="item.is_default_value"
                    :model-value="getRangeValue(item)"
                    style="width: 100%;"
                    @update:model-value="(val: string[]) => updateItemDefaultValue(val, item)" />
                  <audit-icon
                    v-if="hoverDeleteKey === item.raw_name && !item.is_default_value"
                    class="delete"
                    type="delete-fill"
                    @click="updateItemDefaultValue([], item)" />
                </div>
                <bk-input
                  v-else-if="item.field_category === 'inputer'"
                  :disabled="item.is_default_value"
                  :model-value="typeof item.default_value === 'string' ? item.default_value : ''"
                  @change="val => updateItemDefaultValue(val, item)" />
                <bk-tag-input
                  v-else
                  allow-create
                  collapse-tags
                  :disabled="item.is_default_value"
                  has-delete-icon
                  :list="[]"
                  :model-value="getTagValue(item)"
                  @change="val => updateItemDefaultValue(val, item)" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  export interface InputVariableItem {
    raw_name: string;
    display_name: string;
    description: string;
    required: boolean;
    field_category: string;
    is_default_value: boolean;
    default_value: string | Array<string> | Date;
    raw_default_value?: string | Array<string> | Date;
    choices: Array<{
      key: string;
      name: string;
    }>;
  }

  interface Props {
    hasReport: boolean;
    inputVariables: InputVariableItem[];
    reportListsPanels: Array<Record<string, any>>;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const now = new Date();
  const isComExpanded = ref(true);
  const isVarExpanded = ref(true);
  const hoverDeleteKey = ref('');
  const defaultTipVisibleMap = ref<Record<string, boolean>>({});
  const localFields = ref<InputVariableItem[]>([]);

  const cloneItem = (item: InputVariableItem): InputVariableItem => ({
    ...item,
    default_value: Array.isArray(item.default_value) ? [...item.default_value] : item.default_value,
    raw_default_value: Array.isArray(item.raw_default_value) ? [...item.raw_default_value] : item.raw_default_value,
    choices: Array.isArray(item.choices) ? [...item.choices] : [],
  });

  watch(() => props.inputVariables, (list) => {
    localFields.value = Array.isArray(list) ? list.map(cloneItem) : [];
  }, {
    immediate: true,
    deep: true,
  });

  const panelUidSet = computed(() => new Set((props.reportListsPanels || []).map(item => item.uid)));

  const comList = computed(() => localFields.value.filter(item => panelUidSet.value.has(item.description)));
  const variableList = computed(() => localFields.value.filter(item => !panelUidSet.value.has(item.description)));
  const hasNoParam = computed(() => localFields.value.length === 0);

  const getLastMillisecondOfDate = (ts: number) => {
    const date = new Date(ts);
    date.setHours(0, 0, 0, 0);
    return date;
  };

  const dateShortCut: any = [
    { text: '今天', value: () => getLastMillisecondOfDate(now.getTime()), short: 'now/d' },
    { text: '昨天', value: () => getLastMillisecondOfDate(now.getTime() - 24 * 60 * 60 * 1000), short: 'now-1d/d' },
    { text: '前天', value: () => getLastMillisecondOfDate(now.getTime() - 2 * 24 * 60 * 60 * 1000), short: 'now-2d/d' },
    { text: '一星期前', value: () => getLastMillisecondOfDate(now.getTime() - 7 * 24 * 60 * 60 * 1000), short: 'now-7d/d' },
    { text: '一个月前', value: () => getLastMillisecondOfDate(now.getTime() - 30 * 24 * 60 * 60 * 1000), short: 'now-1M/d' },
    { text: '一年前', value: () => getLastMillisecondOfDate(now.getTime() - 365 * 24 * 60 * 60 * 1000), short: 'now-1y/d' },
  ];

  const getPanelTooltip = (item: InputVariableItem) => {
    const matched = props.reportListsPanels.find(panel => panel.uid === item.description);
    return matched?.description || '';
  };

  const findFieldIndex = (rawName: string) => localFields.value.findIndex(item => item.raw_name === rawName);

  const updateField = (rawName: string, patch: Partial<InputVariableItem>) => {
    const index = findFieldIndex(rawName);
    if (index < 0) {
      return;
    }
    localFields.value[index] = {
      ...localFields.value[index],
      ...patch,
    };
  };

  const hideDefaultTip = (rawName: string) => {
    defaultTipVisibleMap.value = {
      ...defaultTipVisibleMap.value,
      [rawName]: false,
    };
  };

  const handleConfirmDefaultTip = (item: InputVariableItem) => {
    hideDefaultTip(item.raw_name);
    updateField(item.raw_name, {
      is_default_value: true,
      default_value: item.raw_default_value ?? '',
    });
  };

  const handleDefaultValueToggle = (checked: boolean | string | number, item: InputVariableItem) => {
    if (checked === true) {
      defaultTipVisibleMap.value = {
        ...defaultTipVisibleMap.value,
        [item.raw_name]: true,
      };
      return;
    }
    hideDefaultTip(item.raw_name);
    updateField(item.raw_name, {
      is_default_value: false,
    });
  };

  const updateItemDefaultValue = (val: any, item: InputVariableItem) => {
    updateField(item.raw_name, {
      default_value: val,
    });
  };

  const getDateValue = (item: InputVariableItem) => (item.default_value instanceof Date ? item.default_value : '');
  const getRangeValue = (item: InputVariableItem) => (Array.isArray(item.default_value) ? item.default_value : []);
  const getTagValue = (item: InputVariableItem) => (Array.isArray(item.default_value) ? item.default_value : []);

  const getFields = () => localFields.value;

  defineExpose({
    getFields,
  });
</script>

<style scoped lang="postcss">
.bkvision-param-config {
  margin-bottom: 16px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 1px 2px 0 #00000029;
}

.param-card-title {
  display: flex;
  height: 52px;
  padding: 0 24px;
  font-size: 14px;
  font-weight: 600;
  color: #313238;
  align-items: center;
}

.param-card-body {
  padding: 0 24px 16px;
}

.param-section {
  & + .param-section {
    margin-top: 8px;
  }
}

.section-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 32px;
  gap: 6px;
  cursor: pointer;

  .section-arrow {
    flex: 0 0 auto;
    font-size: 12px;
    color: #979ba5;
    transition: transform .2s ease;

    &.is-collapsed {
      transform: rotate(-90deg);
    }
  }

  .title-text {
    flex: 0 0 auto;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .title-info-icon {
    width: 14px;
    height: 14px;
    flex: 0 0 auto;
  }

  .title-desc {
    flex: 1;
    overflow: hidden;
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.param-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.param-item {
  width: 100%;
}

.param-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 5px;
  font-size: 12px;
  line-height: 20px;
  color: #4d4f56;
}

.title-right {
  color: #4d4f56;
  cursor: pointer;

  :deep(.bk-checkbox-label) {
    color: #4d4f56;
  }
}

.param-content {
  width: 100%;
}

.range-wrapper {
  position: relative;
}

.delete {
  position: absolute;
  top: 8px;
  right: 10px;
  font-size: 14px;
  color: #c4c6cc;
  cursor: pointer;
}

.default-value-tip-popover {
  width: 230px;
  padding: 0;

  .default-value-tip-text {
    margin: 0 16px 12px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    white-space: normal;
  }

  .default-value-tip-actions {
    display: flex;
    justify-content: flex-end;
    padding: 0 16px 8px;
  }
}
</style>

