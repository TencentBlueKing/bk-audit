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
  <div class="field-cell">
    <!-- 字段显示名 -->
    <template v-if="fieldKey === 'display_name'">
      <field-input
        v-if="localEventItem.prefix"
        ref="displayNameRef"
        v-model="localEventItem.display_name"
        required
        theme="background" />
      <span
        v-else
        class="ml8">
        {{ localEventItem.display_name }}
      </span>
    </template>

    <!-- 是否展示 -->
    <bk-switcher
      v-else-if="fieldKey === 'is_show'"
      v-model="localEventItem.is_show"
      style="margin-left: 8px;"
      theme="primary"
      @change="handleUpdateIsShow" />

    <!-- 是否重点展示 -->
    <bk-switcher
      v-else-if="fieldKey === 'is_priority'"
      v-model="localEventItem.is_priority"
      v-bk-tooltips="{
        content: t('基本信息字段不支持折叠，无需配置'),
        disabled: localEventItem.prefix,
      }"
      :disabled="!localEventItem.is_show || !localEventItem.prefix"
      style="margin-left: 8px;"
      theme="primary" />

    <!-- 是否去重 -->
    <bk-switcher
      v-else-if="fieldKey === 'duplicate_field'"
      v-model="localEventItem.duplicate_field"
      style="margin-left: 8px;"
      theme="primary" />

    <!-- 字段关联 -->
    <field-mapping
      v-else-if="fieldKey === 'map_config' && localEventItem.map_config"
      ref="fieldMappingRef"
      :event-item="eventItem"
      :event-item-key="eventItemKey"
      :optional-fields="optionalFields"
      :required-fields="requiredFields"
      :select-options="selectOptions"
      @add-custom-constant="addCustomConstant"
      @select="handleFieldSelect" />

    <div
      v-else-if="fieldKey === 'enum_mappings' && localEventItem.enum_mappings"
      class="field-cell-div"
      style="width: 100%;cursor: pointer;"
      @click="handleFiledDict">
      <span
        :style="{
          color: localEventItem.enum_mappings.mappings.length ? '#63656e' : '#c4c6cc',
        }">{{ localEventItem.enum_mappings.mappings.length ? t('已配置') : '请点击配置' }}</span>
      <audit-popconfirm
        v-if="localEventItem.enum_mappings.mappings.length"
        :confirm-handler="() => handleRemoveMappings()"
        :content="t('删除操作无法撤回，请谨慎操作！')"
        :title="t('确认删除该配置？')">
        <audit-icon
          class="remove-mappings-btn remove-btn"
          type="delete-fill" />
      </audit-popconfirm>
      <field-dict
        ref="fieldDictRef"
        v-model:showFieldDict="showFieldDict"
        :edit-data="localEventItem.enum_mappings.mappings"
        @submit="handleDictSubmit" />
    </div>

    <!-- 字段下钻 -->
    <template v-else-if="fieldKey === 'drill_config' && localEventItem.drill_config">
      <div
        v-if="!localEventItem.drill_config.length"
        class="field-cell-div"
        style="color: #c4c6cc;"
        @click="() => handleClick()">
        {{ t('请点击配置') }}
      </div>
      <div
        v-else
        class="field-cell-div"
        @click="() => handleClick(localEventItem.drill_config)">
        <bk-popover
          placement="top"
          theme="black">
          <span style="cursor: pointer;">{{ t('已配置工具下钻', { count: localEventItem.drill_config.length }) }}</span>
          <template #content>
            <div>
              <div
                v-for="config in localEventItem.drill_config"
                :key="config.tool.uid">
                • {{ getToolNameAndType(config.tool.uid).name }}
              </div>
            </div>
          </template>
        </bk-popover>
        <!-- 删除 -->
        <audit-popconfirm
          class="ml8"
          :confirm-handler="() => handleRemove()"
          :content="t('移除操作无法撤回，请谨慎操作！')"
          :title="t('确认移除以下工具？')">
          <audit-icon
            class="remove-btn"
            type="delete-fill" />
          <template #content>
            <bk-table
              ref="refTable"
              :columns="columns"
              :data="localEventItem.drill_config"
              height="auto"
              max-height="100%"
              show-overflow-tooltip
              stripe />
          </template>
        </audit-popconfirm>
        <bk-popover
          v-if="localEventItem.drill_config
            .some(drill => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
          placement="top"
          theme="black">
          <audit-icon
            class="renew-tips"
            type="info-fill" />
          <template #content>
            <div>
              <div>{{ t('以下工具已更新，请确认：') }}</div>
              <div
                v-for="drill in localEventItem.drill_config
                  .filter(drill => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
                :key="drill.tool.uid">
                • {{ getToolNameAndType(drill.tool.uid).name }}
              </div>
            </div>
          </template>
        </bk-popover>
      </div>
      <!-- 字段下钻 -->
      <field-reference
        ref="fieldReferenceRef"
        v-model:showFieldReference="showFieldReference"
        :all-tools-data="allToolsData"
        :new-tool-name="strategyName"
        :output-fields="outputFields"
        :tag-data="tagData"
        @open-tool="handleOpenTool"
        @submit="handleFieldSubmit" />
    </template>

    <!-- 描述 -->
    <bk-input
      v-else-if="fieldKey === 'description'"
      v-model="localEventItem.description"
      class="description-input"
      :maxlength="100"
      :show-word-limit="false" />

    <!-- 仅查看 -->
    <span
      v-else
      class="ml8">
      {{ localEventItem[fieldKey] }}
    </span>
  </div>
</template>

<script setup lang="tsx">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';
  import ToolDetailModel from '@model/tool/tool-detail';

  import FieldDict from './field-dict.vue';
  import FieldInput from './field-input.vue';
  import FieldMapping from './field-mapping.vue';

  import FieldReference from '@/views/tools/tools-square/add/components/data-search/components/field-reference/index.vue';

  interface Props {
    eventItem: StrategyFieldEvent['event_basic_field_configs'][0];
    eventItemKey: keyof StrategyFieldEvent;
    fieldKey: keyof StrategyFieldEvent['event_basic_field_configs'][0];
    selectOptions: Array<DatabaseTableFieldModel>;
    strategyName: string;
    outputFields: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      target_field_type: string;
    }>;
    allToolsData: Array<ToolDetailModel>;
    tagData: Array<{
      tag_id: string
      tag_name: string;
      tool_count: number;
    }>;
  }

  interface Emits {
    (e: 'update:fieldValue', value: any): void;
    (e: 'select', value: string, config: StrategyFieldEvent['event_basic_field_configs'][0]): void;
    (e: 'add-custom-constant', value: string): void;
    (e: 'openTool', value: ToolDetailModel): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const requiredFields = ['raw_event_id', 'event_source', 'operator'];
  const optionalFields = ['event_content', 'event_type'];

  const localEventItem = ref(props.eventItem);
  const showFieldReference = ref(false);
  const showFieldDict = ref(false);

  const fieldMappingRef = ref();
  const fieldReferenceRef = ref();
  const displayNameRef = ref();
  const fieldDictRef = ref();

  // const iconMap = {
  //   data_search: 'sqlxiao',
  //   api: 'apixiao',
  //   bk_vision: 'bkvisonxiao',
  // };

  const columns = [{
    label: () => t('工具列表'),
    render: ({ data }: {data: NonNullable<Props['eventItem']['drill_config']>[0]}) => <div>{getToolNameAndType(data.tool.uid).name}</div>,
  }];

  const toolMaxVersionMap = computed(() => props.allToolsData.reduce((res, item) => {
    res[item.uid] = item.version;
    return res;
  }, {} as Record<string, number>));

  const handleFieldSelect = (value: string) => {
    emit('select', value, props.eventItem);
  };

  const handleFiledDict = () => {
    showFieldDict.value = true;
  };

  const handleDictSubmit = (data: Array<{
    key: string;
    name: string;
  }>) => {
    if (localEventItem.value.enum_mappings) {
      localEventItem.value.enum_mappings.mappings = data;
    }
  };

  const addCustomConstant = (value: string) => {
    emit('add-custom-constant', value);
  };

  const handleUpdateIsShow = (value: boolean) => {
    if (!value && localEventItem.value.is_priority && localEventItem.value.prefix) {
      localEventItem.value.is_priority = false;
    }
    if (!localEventItem.value.prefix) {
      localEventItem.value.is_priority = value;
    }
  };

  const handleClick = (drillConfig?: StrategyFieldEvent['event_basic_field_configs'][0]['drill_config']) => {
    showFieldReference.value = true;
    if (drillConfig) {
      fieldReferenceRef.value.setFormData(drillConfig);
    }
  };

  const handleFieldSubmit = (drillConfig: any) => {
    localEventItem.value.drill_config = drillConfig;
  };

  // 删除值
  const handleRemove = async () => {
    localEventItem.value.drill_config = [];
  };

  const handleRemoveMappings = async () => {
    localEventItem.value.enum_mappings =  {
      collection_id: '',
      mappings: [],
    };
  };

  // 打开工具
  const handleOpenTool = async (toolInfo: ToolDetailModel) => {
    emit('openTool', toolInfo);
  };

  const getToolNameAndType = (uid: string) => {
    const tool = props.allToolsData.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };

  watch(() => props.eventItem, (value) => {
    localEventItem.value = value;
  });

  defineExpose({
    getValue() {
      if (!fieldMappingRef.value && !displayNameRef.value) {
        return Promise.resolve();
      }
      if (displayNameRef.value) {
        return displayNameRef.value.getValue();
      }
      if (fieldMappingRef.value) {
        return fieldMappingRef.value.getValue();
      }
    },
  });
</script>

<style lang="postcss" scoped>
.field-cell {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;

  :deep(.bk-input) {
    height: 40px;
    border: none;
  }

  .description-input {
    border: none;
  }

  .field-cell-div {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    height: 100%;
    padding: 0 8px;
    line-height: 33px;
    cursor: pointer;

    &:hover {
      .remove-btn {
        display: block;
      }
    }

    .remove-btn {
      position: absolute;
      top: 38%;
      right: 28px;
      z-index: 1;
      display: none;
      font-size: 12px;
      color: #c4c6cc;
      transition: all .15s;

      &:hover {
        color: #979ba5;
      }
    }

    .remove-mappings-btn {
      top: 40%;
      right: 8px;
    }

    .renew-tips {
      position: absolute;
      right: 8px;
      font-size: 14px;
      color: #3a84ff;
    }
  }
}
</style>
