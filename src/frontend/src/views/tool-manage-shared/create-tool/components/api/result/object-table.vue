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
  <div class="object-table bk-theme-form--inline">
    <div
      class="object-table-head"
      style="background-color: #f5f7fa">
      <audit-icon
        class="move"
        type="move" />
      <span class="head-text">{{ `${data.name}(${data.json_path})` }}</span>
      <bk-tag
        style="margin-left: 10px;background-color: #e1ecff;"
        theme="info">
        {{ t('键值对') }}
      </bk-tag>
      <audit-icon
        class="close"
        type="close"
        @click="handleClose" />
    </div>
    <div class="render-field">
      <div class="field-header-row">
        <div
          class="field-value"
          style="flex: 0 0 200px;background-color: #f0f1f5">
          {{ t('显示名') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 250px;background-color: #f0f1f5">
          {{ t('字段值映射') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 300px;background-color: #f0f1f5">
          {{ t('字段值下钻') }}
        </div>
        <div
          class="field-value"
          style="background-color: #f0f1f5">
          {{ t('字段说明') }}
        </div>
      </div>
    </div>
    <div>
      <audit-form
        ref="formRef"
        form-type="vertical"
        :model="formData">
        <!-- 显示名 -->
        <div class="render-field">
          <div class="field-row">
            <div
              class="field-value"
              style="flex: 0 0 200px;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input v-model="formData.display_name" />
              </bk-form-item>
            </div>
            <div
              class="field-value"
              style="flex: 0 0 250px;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <div class="field-value-div">
                  <span
                    :class="formData.mappings.length === 0 ? `field-span` : `field-span-black`"
                    @click="handleAddDict">
                    {{ t(formData.mappings.length === 0 ? '请点击配置' : '已配置') }}
                  </span>
                  <audit-popconfirm
                    v-if="formData.mappings.length"
                    ref="mappingsPopconfirmRefs"
                    :confirm-handler="() => handleRemoveMappings()"
                    :content="t('删除操作无法撤回，请谨慎操作！')"
                    :title="t('确认删除该配置？')"
                    @hide="handleMappingsPopconfirmHide">
                    <audit-icon
                      class="remove-mappings-btn remove-btn"
                      :class="{ 'is-popconfirm-visible': mappingsPopconfirmVisible }"
                      type="delete-fill"
                      @click="handleMappingsPopconfirmShow" />
                  </audit-popconfirm>
                </div>
              </bk-form-item>
            </div>
            <div
              class="field-value"
              style="flex: 0 0 300px;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <div
                  class="field-value-div">
                  <template v-if="formData.drill_config && formData.drill_config.length > 0">
                    <bk-popover
                      placement="top"
                      theme="black">
                      <span
                        @click="handleClick(formData.drill_config)">
                        {{ t('已配置') }}
                        <span style="color: #3a84ff;">{{ formData.drill_config.length }}</span>
                        {{ t('个工具') }}
                      </span>
                      <template #content>
                        <div>
                          <div
                            v-for="config in formData.drill_config"
                            :key="config.tool.uid">
                            {{ getToolNameAndType(config.tool.uid).name }}
                          </div>
                        </div>
                      </template>
                    </bk-popover>
                    <!-- 删除 -->
                    <audit-popconfirm
                      ref="drillPopconfirmRefs"
                     
                      :confirm-handler="() => handleRemove()"
                      :content="t('移除操作无法撤回，请谨慎操作！')"
                      :title="t('确认移除以下工具？')" style="margin-left: var(--bk-theme-space-8)">
                      <audit-icon
                        class="remove-btn"
                        :class="{ 'is-popconfirm-visible': drillPopconfirmVisible }"
                        type="delete-fill" />
                      <template #content>
                        <bk-table
                          ref="refTable"
                          :columns="columns"
                          :data="formData.drill_config"
                          height="auto"
                          max-height="100%"
                          show-overflow-tooltip
                          stripe />
                      </template>
                    </audit-popconfirm>
                    <bk-popover
                      v-if="formData.drill_config
                        .some((drill: any) => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
                      placement="top"
                      theme="black">
                      <audit-icon
                        class="renew-tips"
                        type="info-fill" />
                      <template #content>
                        <div>
                          <div>{{ t('以下工具已更新，请确认：') }}</div>
                          <div
                            v-for="item in formData.drill_config
                              // eslint-disable-next-line max-len
                              .filter((drill: any) => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
                            :key="item.tool.uid">
                            {{ getToolNameAndType(item.tool.uid).name }}
                          </div>
                        </div>
                      </template>
                    </bk-popover>
                  </template>
                  <span
                    v-else
                    style="color: #c4c6cc;"
                    @click="handleClick()">
                    {{ t('请点击配置') }}
                  </span>
                </div>
              </bk-form-item>
            </div>
            <div
              class="field-value"
              style="border-right: 0;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input v-model="formData.description" />
              </bk-form-item>
            </div>
          </div>
        </div>
      </audit-form>
    </div>
    <!-- 字段映射 -->
    <field-dict
      ref="fieldDictRef"
      v-model:showFieldDict="showFieldDict"
      :edit-data="enumMappingsData"
      @submit="handleDictSubmit" />

    <!-- 字段下钻 -->
    <field-reference
      ref="fieldReferenceRef"
      v-model:showFieldReference="showFieldReference"
      :all-tools-data="allToolsData"
      :new-tool-name="newToolDataName"
      :output-fields="fieldsData"
      :tag-data="toolTagData"
      @open-tool="handleOpenTool"
      @refresh-tool-list="handleRefreshToolList"
      @submit="handleFieldSubmit" />
    <!-- 循环所有工具 -->
    <div
      v-for="item in allOpenToolsData"
      :key="item">
      <component
        :is="DialogVue"
        :ref="(el:any) => dialogRefs[item] = el"
        :all-tools-data="allToolsData"
        :tags-enums="toolTagData"
        @open-field-down="openFieldDown" />
    </div>
  </div>
</template>
<script setup lang='tsx'>
  import type { Column } from 'bkui-vue/lib/table/props';
  import { computed, type ComputedRef, inject, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import resultDataModel from '@model/tool/api';

  import DialogVue from '@views/tools/tools-square/components/dialog/dialog.vue';
  import { useToolManageContext } from '@views/tool-manage-shared/context';

  import FieldReference from '../../data-search/components/field-reference/index.vue';

  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';
  import fieldDict from '@/views/strategy-manage/strategy-create/components/step2/components/event-table/field-dict.vue';

  interface drill {
    drill_config: Array<{
      tool: {
        uid: string;
        version: number;
      };
      config: Array<{
        source_field: string;
        target_value_type: string;
        target_value: string;
        target_field_type: string;
      }>;
      drill_name?: string;
    }>;
  }

  interface FieldItem {
    raw_name: string;
    display_name: string;
    description: string;
    json_path: string;
    children: FieldItem[];
  }

  interface Props {
    data: any, // 当前节点的数据
    outputFields: any, // 输出字段
    treeData: Array<resultDataModel>, // 树形数据
    listData: Array<any>, // 列表数据
  }
  interface Emits {
    (e: 'close', id: string): void
    (e: 'configChange', data: any, path: string): void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const toolManageCtx = useToolManageContext();
  const fieldReferenceRef = ref();

  // 使用工具对话框hooks
  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
    handleOpenTool,
  } = useToolDialog();

  const formData = ref({
    display_name: '',
    description: '',
    mappings: [],
    drill_config: [] as drill['drill_config'],
  });
  const showFieldDict = ref(false);
  const enumMappingsData = ref<any[]>([]);
  const showFieldReference = ref(false);
  const toolMaxVersionMap = ref<Record<string, number>>({});
  const drillPopconfirmVisible = ref();
  const mappingsPopconfirmVisible = ref();

  const columns = [{
    label: () => t('工具列表'),
    render: ({ data }: {data: any}) => <div>{getToolNameAndType(data.tool.uid).name}</div>,
  }] as Column[];


  const newToolDataName = inject<ComputedRef<string>>('newToolDataName', computed(() => ''));

  // 转换树形数据，保持树状结构（kv模式不能引用表格中的字段, 即node.list中的不添加）
  const transformTreeData = (nodes: any[]): FieldItem[] => {
    if (!Array.isArray(nodes)) {
      return [];
    }
    return nodes
      .filter((node: any) => !node.list || node.list.length === 0)
      .map((node: any) => {
        const listItem = props.listData.find((item: any) => item.json_path === node.json_path);
        return {
          raw_name: node.name || '',
          display_name: listItem?.config?.display_name || '',
          description: listItem?.config?.description || '',
          json_path: node.json_path || '',
          children: node.children && node.children.length > 0
            ? transformTreeData(node.children)
            : [],
        };
      });
  };

  // 使用 computed 创建 fieldsData，保持树状结构
  const fieldsData = computed<FieldItem[]>(() => {
    if (!props.treeData) {
      return [];
    }
    return transformTreeData(props.treeData);
  });

  const handleClick = (drillConfig?: drill['drill_config']) => {
    showFieldReference.value = true;
    // 编辑
    if (drillConfig) {
      fieldReferenceRef.value.setFormData(drillConfig);
    }
  };

  // 点击字段映射
  const handleAddDict = () => {
    enumMappingsData.value = formData.value.mappings;
    showFieldDict.value = true;
  };

  const handleDictSubmit = (data: any) => {
    showFieldDict.value = false;
    formData.value.mappings = data;
  };

  // 删除字段值映射
  const handleRemoveMappings = async () => {
    formData.value.mappings = [];
  };

  const handleMappingsPopconfirmHide = () => {
    mappingsPopconfirmVisible.value = false;
  };

  const handleMappingsPopconfirmShow = () => {
    mappingsPopconfirmVisible.value = true;
  };

  // 获取可用于下钻的工具列表（平台/场景由 context 注入）
  const {
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(toolManageCtx.fetchTools as any, {
    defaultValue: [] as any[],
    defaultParams: toolManageCtx.getToolsDefaultParams(),
    onSuccess: (data: any[]) => {
      toolMaxVersionMap.value = data.reduce((res: Record<string, number>, item: any) => {
        res[item.uid] = item.version;
        return res;
      }, {} as Record<string, number>);
    },
  });

  // 获取标签列表
  const {
    data: toolTagData,
  } = useRequest(toolManageCtx.fetchTags as any, {
    defaultValue: [] as any[],
    manual: true,
    onSuccess: () => {
      if (toolManageCtx.refreshToolsAfterTags) {
        fetchAllTools(toolManageCtx.getToolsDefaultParams());
      }
    },
  });

  const handleRefreshToolList = () => {
    fetchAllTools(toolManageCtx.getToolsDefaultParams());
  };
  // 点击字段下钻
  const handleFieldSubmit = (data: any) => {
    showFieldReference.value = false;
    formData.value.drill_config = data;
  };
  // 删除值
  const  handleRemove = async () => {
    formData.value.drill_config = [];
    return Promise.resolve();
  };
  // 获取工具名称和类型
  const getToolNameAndType = (uid: string) => {
    const tool = allToolsData.value.find((item: any) => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };

  // 关闭
  const handleClose = () => {
    emits('close', props.data);
  };

  watch(() => formData.value, (val) => {
    if (val) {
      emits('configChange', val, props.data.json_path);
    }
  }, {
    immediate: true,
    deep: true,
  });

  watch(() => props.outputFields, (val) => {
    if (val) {
      val.forEach((el: any) => {
        if (el.raw_name === props.data.name) {
          formData.value.display_name = el.display_name;
          formData.value.description = el.description;
          formData.value.drill_config = el.drill_config;
          formData.value.mappings = el.enum_mappings.mappings;
        }
      });
    }
  }, {
    immediate: true,
    deep: true,
  });
</script>
<style lang="postcss" scoped>
.object-table {
  position: relative;
  margin-top: var(--bk-theme-space-12);
  border: 1px solid var(--bk-theme-border-default);
  border-radius: var(--bk-theme-tag-radius);

  .object-table-head {
    display: flex;
    height: 31px;
    background: var(--bk-theme-surface-muted);
    border-bottom: 1px solid var(--bk-theme-border-default);
    align-items: center;

    .move {
      margin-left: var(--bk-theme-space-4);
      color: var(--bk-theme-border-strong);
      cursor: move;
    }

    .head-text {
      margin-left: var(--bk-theme-space-4);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0;
      color: var(--bk-theme-text-default);
    }

    .close {
      position: absolute;
      right: 5px;
      color: var(--bk-theme-text-weak);
      cursor: pointer;
    }
  }
}

.render-field {
  display: flex;
  min-width: 640px;
  overflow: hidden;
  border-top: 1px solid var(--bk-theme-border-default);
  border-radius: var(--bk-theme-tag-radius);
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-select {
    width: 40px;
    text-align: center;
    background: var(--bk-theme-table-header-bg);
  }

  .field-operation {
    width: 170px;
    padding-left: var(--bk-theme-space-16);
    background: var(--bk-theme-table-header-bg);
    border-left: 1px solid var(--bk-theme-border-default);
  }


}

:deep(.field-value) {
  display: flex;
  flex: 1;

  /* width: 180px; */
  overflow: hidden;
  border-right: 1px solid var(--bk-theme-border-default);
  align-items: center;

  &:first-child {
    border-left: none;
  }

  .field-value-div {
    display: flex;
    padding: 0 var(--bk-theme-space-8);
    cursor: pointer;
    align-items: center;

    &:hover {
      .remove-btn {
        display: block;
      }
    }

    .remove-btn {
      position: absolute;
      top: 36%;
      right: 28px;
      z-index: 1;
      display: none;
      font-size: 12px;
      color: var(--bk-theme-border-strong);
      transition: all .15s;

      &:hover {
        color: var(--bk-theme-text-weak);
      }

      &.is-popconfirm-visible {
        display: block;
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
      color: var(--bk-theme-color-brand-2);
    }
  }

  .bk-form-item.is-error {
    .bk-input--text {background-color: var(--bk-theme-fill-danger);
    }
  }

  .bk-form-item {
    width: 100%;

    .bk-input,
    .bk-date-picker-editor,
    .bk-select-trigger,
    .bk-select-tag,
    .date-picker {
      height: 42px !important;
      border: none;
    }

    .icon-wrapper {
      top: 6px;
    }

    .bk-input.is-focused:not(.is-readonly) {
      border: 1px solid var(--bk-theme-color-brand-2);
      outline: 0;
     
    }

    .bk-form-error-tips {
      top: 12px
    }
  }
}

.field-header-row {
  display: flex;
  height: 42px;
  font-size: 12px;
  line-height: 40px;
  color: var(--bk-theme-text-strong);
  background: var(--bk-theme-surface-muted);

  .field-value {
    padding-left: var(--bk-theme-space-8);
  }

  .field-value.is-required {
    &::after {
      margin-left: var(--bk-theme-space-4);
      color: red;
      content: '*';
    }
  }

  .field-select,
  .field-operation {
    background: var(--bk-theme-surface-muted);
  }
}

.field-row {
  display: flex;
  overflow: hidden;
  font-size: 12px;
  line-height: 42px;
  color: var(--bk-theme-text-default);
  border-right: 1px solid var(--bk-theme-border-default);
}

.field-icon {
  margin-left: var(--bk-theme-space-16);
  color: var(--bk-theme-border-strong);
}

.field-span {
  margin-left: var(--bk-theme-space-4);
  color: var(--bk-theme-border-strong);
  cursor: pointer;
}

.field-span-black {
  margin-left: var(--bk-theme-space-4);
  color: var(--bk-theme-text-default);
  cursor: pointer;
}
</style>
