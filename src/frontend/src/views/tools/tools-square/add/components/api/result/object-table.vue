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
  <div class="object-table">
    <div class="object-table-head">
      <audit-icon
        class="move"
        type="move" />
      <span class="head-text">{{ data.name }}</span>
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
          style="flex: 0 0 200px;">
          {{ t('显示名') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 250px;">
          {{ t('字段值映射') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 300px;">
          {{ t('字段值下钻') }}
        </div>
        <div
          class="field-value">
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
                <span
                  :class="formData.mappings.length === 0 ? `field-span` : `field-span-black`"
                  @click="handleAddDict"> {{ t(formData.mappings.length === 0 ? '请点击配置' : '已配置') }} </span>
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
                  <template v-if="formData.drill_config.length > 0">
                    <bk-popover
                      placement="top"
                      theme="black">
                      <span
                        @click="() => handleClick">
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
                      :ref="(el: any) => drillPopconfirmRefs[0] = el"
                      class="ml8"
                      :confirm-handler="() => handleRemove()"
                      :content="t('移除操作无法撤回，请谨慎操作！')"
                      :title="t('确认移除以下工具？')">
                      <audit-icon
                        class="remove-btn"
                        :class="{ 'is-popconfirm-visible': drillPopconfirmVisible[0] }"
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
                    @click="handleClick">
                    {{ t('请点击配置') }}
                  </span>
                </div>
              </bk-form-item>
            </div>
            <div
              class="field-value">
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
      :new-tool-name="data.name"
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
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import DialogVue from '@views/tools/tools-square/components/dialog.vue';

  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';
  import fieldDict from '@/views/strategy-manage/strategy-create/components/step2/components/event-table/field-dict.vue';
  import FieldReference from '@/views/tools/tools-square/add/components/data-search/components/field-reference/index.vue';

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

  interface Props {
    data: any,
    outputFields: any,
    treeData: any,
  }
  interface Emits {
    (e: 'close', id: string): void
    (e: 'configChange', data: any, path: string): void
  }
  interface Exposes {
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const formData = ref({
    display_name: '',
    description: '',
    mappings: [],
    drill_config: [] as drill['drill_config'],
  });
  const fieldsData = ref([{
    raw_name: '',
    display_name: '',
    description: '',
  }]);
  const showFieldDict = ref(false);
  const enumMappingsData = ref<any[]>([]);
  const fieldDictRef = ref();
  const showFieldReference = ref(false);
  const toolMaxVersionMap = ref<Record<string, number>>({});
  const drillPopconfirmVisible = ref<Record<number, boolean>>({});

  const columns = [{
    label: () => t('工具列表'),
    render: ({ data }: {data: any}) => <div>{getToolNameAndType(data.tool.uid).name}</div>,
  }] as Column[];

  const drillPopconfirmRefs = ref<Record<number, any>>({});

  const handleClick = () => {
    showFieldReference.value = true;
  };
  // 使用工具对话框hooks
  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
    handleOpenTool,
  } = useToolDialog();
  // 点击字段映射
  const handleAddDict = () => {
    enumMappingsData.value = formData.value.mappings;
    showFieldDict.value = true;
  };

  const handleDictSubmit = (data: any) => {
    showFieldDict.value = false;
    formData.value.mappings = data;
  };
  // 获取所有工具
  const {
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    onSuccess: (data) => {
      toolMaxVersionMap.value = data.reduce((res, item) => {
        res[item.uid] = item.version;
        return res;
      }, {} as Record<string, number>);
    },
  });
  // 获取标签列表
  const {
    data: toolTagData,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      fetchAllTools();
    },
  });

  const handleRefreshToolList = () => {
    fetchAllTools();
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
    const tool = allToolsData.value.find(item => item.uid === uid);
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
  // 递归遍历树形数据，收集所有叶子节点
  const traverseTree = (nodes: any[]): any[] => {
    const result: any[] = [];
    nodes.forEach((node: any) => {
      if (node.children && node.children.length > 0) {
        // 如果有子节点，递归遍历子节点
        result.push(...traverseTree(node.children));
      } else {
        // 如果没有子节点，添加到结果中
        result.push({
          raw_name: node.name,
          display_name: '',
          description: '',
        });
      }
    });
    return result;
  };

  watch(() => formData.value, (val) => {
    if (val) {
      fieldsData.value = traverseTree(props.treeData);
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
  defineExpose<Exposes>({
  });
</script>
<style lang="postcss" scoped>
.object-table {
  position: relative;
  margin-top: 20px;
  border: 1px solid #dcdee5;
  border-radius: 2px;

  .object-table-head {
    display: flex;
    height: 31px;
    background: #f0f1f5;
    box-shadow: 0 1px 0 0 #dcdee5;
    align-items: center;

    .move {
      margin-left: 5px;
      color: #c4c6cc;
      cursor: move;
    }

    .head-text {
      margin-left: 5px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0;
      color: #4d4f56;
    }

    .close {
      position: absolute;
      right: 5px;
      color: #979ba5;
      cursor: pointer;
    }
  }
}

.render-field {
  display: flex;
  min-width: 640px;
  overflow: hidden;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-select {
    width: 40px;
    text-align: center;
    background: #fafbfd;
  }

  .field-operation {
    width: 170px;
    padding-left: 16px;
    background: #fafbfd;
    border-left: 1px solid #dcdee5;
  }


}

:deep(.field-value) {
  display: flex;
  flex: 1;

  /* width: 180px; */
  overflow: hidden;
  border-left: 1px solid #dcdee5;
  align-items: center;

  .field-value-div {
    display: flex;
    padding: 0 8px;
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
      color: #c4c6cc;
      transition: all .15s;

      &:hover {
        color: #979ba5;
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
      color: #3a84ff;
    }
  }

  .bk-form-item.is-error {
    .bk-input--text {
      background-color: #ffebeb;
    }
  }

  .bk-form-item {
    width: 100%;
    margin-bottom: 0;

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
      border: 1px solid #3a84ff;
      outline: 0;
      box-shadow: 0 0 3px #a3c5fd;
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
  color: #313238;
  background: #f0f1f5;

  .field-value {
    padding-left: 8px;
  }

  .field-value.is-required {
    &::after {
      margin-left: 4px;
      color: red;
      content: '*';
    }
  }

  .field-select,
  .field-operation {
    background: #f0f1f5;
  }
}

.field-row {
  display: flex;
  overflow: hidden;
  font-size: 12px;
  line-height: 42px;
  color: #63656e;
  border-right: 1px solid #dcdee5;
  border-bottom: 1px solid #dcdee5;
}

.field-icon {
  margin-left: 20px;
  color: #c4c6cc;
}

.field-span {
  margin-left: 5px;
  color: #c4c6cc;
  cursor: pointer;
}

.field-span-black {
  margin-left: 5px;
  color: black;
  cursor: pointer;
}
</style>
