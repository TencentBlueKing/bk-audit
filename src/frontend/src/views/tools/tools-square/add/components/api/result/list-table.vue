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
  <div class="list-table">
    <div class="list-table-head">
      <audit-icon
        class="move"
        type="move" />
      <span class="head-text">{{ `${data.name}(${data.json_path})` }}</span>
      <bk-tag
        style="margin-left: 10px;background-color: #fdeed8;"
        theme="warning">
        {{ t('表格') }}
      </bk-tag>
      <audit-icon
        class="close"
        type="close"
        @click="handleClose" />
    </div>
    <div class="list-table-body">
      <div class="list-info">
        <bk-input
          v-model="listInfo.name"
          class="mb8"
          style="width: 400px;"
          @change="handleListInfoChange">
          <template #prefix>
            <span class="info-prefix">{{ t('表格显示名') }} </span>
          </template>
        </bk-input>
        <bk-input
          v-model="listInfo.desc"
          class="mb8"
          style="width: 100%;margin-left: 20px;"
          @change="handleListInfoChange">
          <template #prefix>
            <span class="info-prefix">{{ t('表格说明') }} </span>
          </template>
        </bk-input>
      </div>
      <div class="list-content">
        <div class="content-title">
          {{ t('表格字段设置') }}
        </div>
        <div class="content">
          <div class="render-field">
            <div class="field-header-row">
              <div
                class="field-value"
                style="flex: 0 0 200px;border-left: none;">
                {{ t('字段名') }}
              </div>
              <div
                class="field-value"
                style="flex: 0 0 250px;">
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
                {{ t('字段下钻') }}
              </div>
              <div
                class="field-value">
                <span
                  v-bk-tooltips="{ content: t('在查询结果页，鼠标移入label，即可显示字段说明') }"
                  class="underline-dashed">{{ t('字段说明') }}</span>
              </div>
              <div
                class="field-value"
                style="flex: 0 0 50px;" />
            </div>
          </div>
          <vuedraggable
            class="draggable-box"
            :group="{
              name: 'field',
              pull: false,
              push: true
            }"
            item-key="key"
            :list="list">
            <template #item="{ element, index }">
              <div>
                <div class="render-field">
                  <div class="field-row">
                    <div
                      class="field-value"
                      style="flex: 0 0 200px;border-left: none;">
                      <audit-icon
                        class="field-value-move"
                        type="move" />
                      <span class="field-value-text">
                        <tooltips :data="element.name" />
                      </span>
                    </div>
                    <div
                      class="field-value"
                      style="flex: 0 0 250px;">
                      <bk-form-item
                        error-display-type="tooltips"
                        label=""
                        label-width="0">
                        <bk-input v-model="element.display_name" />
                      </bk-form-item>
                    </div>
                    <div
                      class="field-value"
                      style="flex: 0 0 250px;background-color: #fff;">
                      <bk-form-item
                        error-display-type="tooltips"
                        label=""
                        label-width="0">
                        <div class="field-value-div">
                          <span
                            :class="element?.enum_mappings?.mappings.length === 0 ? `field-span` : `field-span-black`"
                            @click="handleAddEnumMapping(element)">
                            {{ t(element?.enum_mappings?.mappings.length === 0 ? '请点击配置' : '已配置') }}
                          </span>
                          <audit-popconfirm
                            v-if="element?.enum_mappings?.mappings.length"
                            :ref="(el: any) => mappingsPopconfirmRefs[index] = el"
                            :confirm-handler="() => handleRemoveMappings(index)"
                            :content="t('删除操作无法撤回，请谨慎操作！')"
                            :title="t('确认删除该配置？')"
                            @hide="() => handleMappingsPopconfirmHide(index)">
                            <audit-icon
                              class="remove-mappings-btn remove-btn"
                              :class="{ 'is-popconfirm-visible': mappingsPopconfirmVisible[index] }"
                              type="delete-fill"
                              @click="() => handleMappingsPopconfirmShow(index)" />
                          </audit-popconfirm>
                        </div>
                      </bk-form-item>
                    </div>
                    <div
                      class="field-value"
                      style="flex: 0 0 300px;background-color: #fff;">
                      <bk-form-item
                        error-display-type="tooltips"
                        label=""
                        label-width="0">
                        <div
                          class="field-value-div"
                          @mouseleave="() => handleDrillMouseLeave(index)">
                          <template v-if="element.drill_config && element.drill_config.length > 0">
                            <bk-popover
                              placement="top"
                              theme="black">
                              <span
                                @click="() => handleClick(element.json_path, element.drill_config)">
                                {{ t('已配置') }}
                                <span style="color: #3a84ff;">{{ element.drill_config?.length }}</span>
                                {{ t('个工具') }}
                              </span>
                              <template #content>
                                <div>
                                  <div
                                    v-for="config in element.drill_config"
                                    :key="config.tool.uid">
                                    {{ getToolNameAndType(config.tool.uid).name }}
                                  </div>
                                </div>
                              </template>
                            </bk-popover>
                            <!-- 删除 -->
                            <audit-popconfirm
                              :ref="(el: any) => drillPopconfirmRefs[index] = el"
                              class="ml8"
                              :confirm-handler="() => handleRemove(index)"
                              :content="t('移除操作无法撤回，请谨慎操作！')"
                              :title="t('确认移除以下工具？')"
                              @hide="() => handleDrillPopconfirmHide(index)">
                              <audit-icon
                                class="remove-btn"
                                :class="{ 'is-popconfirm-visible': drillPopconfirmVisible[index] }"
                                type="delete-fill"
                                @click="() => handleDrillPopconfirmShow(index)" />
                              <template #content>
                                <bk-table
                                  ref="refTable"
                                  :columns="columns"
                                  :data="element.drill_config"
                                  height="auto"
                                  max-height="100%"
                                  show-overflow-tooltip
                                  stripe />
                              </template>
                            </audit-popconfirm>
                            <bk-popover
                              v-if="element.drill_config
                                .some((drill:any) => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
                              placement="top"
                              theme="black">
                              <audit-icon
                                class="renew-tips"
                                type="info-fill" />
                              <template #content>
                                <div>
                                  <div>{{ t('以下工具已更新，请确认：') }}</div>
                                  <div
                                    v-for="drill in element.drill_config
                                      // eslint-disable-next-line max-len
                                      .filter((drill: any) => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
                                    :key="drill.tool.uid">
                                    {{ getToolNameAndType(drill.tool.uid).name }}
                                  </div>
                                </div>
                              </template>
                            </bk-popover>
                          </template>
                          <span
                            v-else
                            style="color: #c4c6cc;"
                            @click="() => handleClick(element.json_path)">
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
                        <bk-input v-model="element.description" />
                      </bk-form-item>
                    </div>
                    <div
                      class="field-value"
                      style="flex: 0 0 50px;border-right: none !important;">
                      <audit-icon
                        class="reduce-fill field-icon"
                        type="reduce-fill"
                        @click="handleDelect(element.json_path)" />
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </vuedraggable>
          <div
            v-if="addList.length > 0"
            class="add-field">
            <bk-popover
              ref="requiredListRef"
              allow-html
              :content="`#${popoverContentId}`"
              ext-cls="field-required-pop"
              placement="top"
              theme="light"
              trigger="click">
              <span>
                <audit-icon
                  class="plus-circle"
                  type="plus-circle" />
                <span class="plus-circle-text"> 添加字段</span>
              </span>
            </bk-popover>
            <div style="display: none">
              <div
                :id="popoverContentId"
                class="field-required-pop-hideen">
                <div
                  v-for="(item, index) in addList"
                  :key="index"
                  class="field-required-item"
                  @click="handleAddList(item)">
                  {{ item.name }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
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
  import { computed, type ComputedRef, inject, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import ToolManageService from '@service/tool-manage';

  import resultDataModel from '@model/tool/api';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import DialogVue from '@views/tools/tools-square/components/dialog.vue';

  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';
  import fieldDict from '@/views/strategy-manage/strategy-create/components/step2/components/event-table/field-dict.vue';
  import FieldReference from '@/views/tools/tools-square/add/components/data-search/components/field-reference/index.vue';

  interface Props {
    data: any,
    outputFields: any,
    treeData: Array<resultDataModel>,
    // isGrouping: boolean
  }
  interface Emits {
    (e: 'close', id: string): void
    (e: 'listConfigChange', data: any, path: string, listInfo: any): void
  }
  interface FieldItem {
    raw_name: string;
    display_name: string;
    description: string;
    json_path: string;
    children: FieldItem[];
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const fieldReferenceRef = ref();
  const listInfo = ref({
    name: '',
    desc: '',
  });
  const list = ref<any[]>([]);
  const addList = ref<any[]>([]);
  const showFieldDict = ref(false);
  const showFieldReference = ref(false);

  const mappingsPopconfirmRefs = ref<Record<number, any>>({});
  const mappingsPopconfirmVisible = ref<Record<number, boolean>>({});
  const drillPopconfirmRefs = ref<Record<number, any>>({});
  const drillPopconfirmVisible = ref<Record<number, boolean>>({});
  const toolMaxVersionMap = ref<Record<string, number>>({});

  const enumMappingsData = ref<any[]>([]);
  // 点击字段映射记录id
  const enumMappingsId = ref('');
  // 点击字段下钻记录id
  const fieldDictId = ref('');

  const newToolDataName = inject<ComputedRef<string>>('newToolDataName', computed(() => ''));

  // 为每个表格实例生成唯一的 popover content ID
  const popoverContentId = computed(() => {
    // 使用 json_path 生成唯一 ID，替换特殊字符
    const uniqueId = props.data?.json_path?.replace(/[^a-zA-Z0-9]/g, '_') || `popover_${Date.now()}`;
    return `hidden_pop_content_add_${uniqueId}`;
  });

  // 转换树形数据
  const transformTreeData = (nodes: any[]): FieldItem[] => {
    if (!Array.isArray(nodes)) {
      return [];
    }
    return nodes.map((node: any) => ({
      raw_name: node.name || '',
      display_name: node.display_name || '',
      description: node.description || '',
      json_path: node.json_path || '',
      children: [],
    }));
  };

  // 使用 computed 创建 fieldsData
  const fieldsData = computed<FieldItem[]>(() => {
    // 只使用当前table字段
    if (!props.data || !props.data.list) {
      return [];
    }
    return transformTreeData(props.data.list);
  });

  // 关闭
  const handleClose = () => {
    emits('close', props.data);
  };

  // 点击字段映射
  const handleAddEnumMapping = (element: any) => {
    enumMappingsId.value = element.json_path;
    enumMappingsData.value = element.enum_mappings?.mappings || [];
    showFieldDict.value = true;
  };

  // 字段映射提交
  const handleDictSubmit = (data: any) => {
    list.value = list.value.map((item: any) => {
      if (item.json_path === enumMappingsId.value) {
        // eslint-disable-next-line no-param-reassign
        item.enum_mappings.mappings = data;
      }
      return item;
    });
  };

  const columns = [{
    label: () => t('工具列表'),
    render: ({ data }: {data: any}) => <div>{getToolNameAndType(data.tool.uid).name}</div>,
  }] as Column[];

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

  const handleClick = (id: string, drillConfig?: any) => {
    fieldDictId.value = id;
    showFieldReference.value = true;
    // 编辑
    if (drillConfig) {
      fieldReferenceRef.value.setFormData(drillConfig);
    }
  };
  // 删除值
  const  handleRemove = async (index: number) => {
    list.value[index].drill_config = [];
  };
  // 字段下钻气泡框显示/隐藏处理
  const handleDrillPopconfirmShow = (index: number) => {
    drillPopconfirmVisible.value[index] = true;
  };

  const handleDrillPopconfirmHide = (index: number) => {
    drillPopconfirmVisible.value[index] = false;
  };

  const handleDrillMouseLeave = (index: number) => {
    // 如果气泡框未显示，则关闭气泡框
    if (drillPopconfirmRefs.value[index] && !drillPopconfirmVisible.value[index]) {
      drillPopconfirmRefs.value[index].hide();
    }
  };

  const handleRemoveMappings = async (index: number) => {
    list.value[index].enum_mappings = {
      collection_id: '',
      mappings: [],
    };
  };

  const handleMappingsPopconfirmHide = (index: number) => {
    mappingsPopconfirmVisible.value[index] = false;
  };

  // 字段值映射气泡框显示/隐藏处理
  const handleMappingsPopconfirmShow = (index: number) => {
    mappingsPopconfirmVisible.value[index] = true;
  };

  // 使用工具对话框hooks
  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
    handleOpenTool,
  } = useToolDialog();
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
  // 提交字段下钻
  const handleFieldSubmit = (data: any) => {
    showFieldReference.value = false;
    list.value = list.value.map((item: any) => {
      if (item.json_path === fieldDictId.value) {
        // eslint-disable-next-line no-param-reassign
        item.drill_config = data || [];
      }
      return item;
    });
  };

  // 移除
  const handleDelect = (path: string) => {
    // list 移除项目
    list.value = list.value.filter((item: any) => item.json_path !== path);
  };
  // 添加
  const handleAddList = (item: any) => {
    // 将项目添加到list.value
    list.value = [...list.value, item];
    // 从addList.value中移除项目
    addList.value = addList.value.filter((addItem: any) => addItem.json_path !== item.json_path);
  };

  // 在树形结构中查找节点的函数
  const findNode = (treeData: any[], targetJsonPath: string): any => {
    if (!treeData || !Array.isArray(treeData)) return null;
    for (const node of treeData) {
      if (node.json_path === targetJsonPath) {
        return node;
      }

      if (node.children && node.children.length > 0) {
        const foundInChildren = findNode(node.children, targetJsonPath);
        if (foundInChildren) {
          return foundInChildren;
        }
      }

      if (node.list && node.list.length > 0) {
        const foundInList = findNode(node.list, targetJsonPath);
        if (foundInList) {
          return foundInList;
        }
      }
    }
    return null;
  };

  const handleListInfoChange = () => {
    emits('listConfigChange', list.value, props.data.json_path, listInfo.value);
  };
  watch(() => list.value, (val) => {
    addList.value = [];
    emits('listConfigChange', val, props.data.json_path, listInfo.value);
    const node = findNode(props.treeData, props.data.json_path);
    // 过滤出node.list中不在当前val中的项目，并保持数据结构一致
    const valJsonPaths = val.map((item: any) => item.json_path);
    addList.value = node.list.filter((item: any) => !valJsonPaths.includes(item.json_path))
      .map((item: any) => {
        // 查找val中对应的项目，如果有则使用val中的完整结构，否则使用基础结构
        const existingItem = val.find((valItem: any) => valItem.json_path === item.json_path);
        return existingItem ? { ...existingItem } : {
          ...item,
          display_name: '',
          description: '',
          drill_config: [],
          enum_mappings: {
            mappings: [],
          },
        };
      });
  }, {
    deep: true,
  });

  watch(() => props.outputFields, (val: any) => {
    if (val && val.length > 0) {
      nextTick(() => {
        // 查找匹配的元素
        const matchedEl = val.find((el: any) => el.json_path === props.data.json_path);
        if (matchedEl) {
          listInfo.value.name = matchedEl.display_name || '';
          listInfo.value.desc = matchedEl.description || '';
          list.value = (matchedEl.field_config?.output_fields || []).map((outItem: any) => {
            const foundNode = props.data?.list?.find((e: any) => e.json_path === outItem.json_path) || {};
            return {
              ...foundNode,
              display_name: outItem.display_name || '',
              description: outItem.description || '',
              drill_config: outItem.drill_config || [],
              enum_mappings: {
                mappings: outItem.enum_mappings?.mappings || [],
              },
            };
          });
        } else {
          // 没有找到匹配项时，使用默认值
          list.value = props.data.list.map((item: any) => ({
            ...item,
            display_name: '',
            enum_mappings: {
              mappings: [],
            },
            drill_config: [],
            description: '',
          }));
        }
      });
    } else {
      list.value = props.data.list.map((item: any) => ({
        ...item,
        display_name: '',
        enum_mappings: {
          mappings: [],
        },
        drill_config: [],
        description: '',
      }));
    }
  }, {
    immediate: true,
    deep: true,
  });
</script>
<style lang="postcss" scoped>
.list-table {
  position: relative;
  margin-top: 6px;
  border: 1px solid #dcdee5;
  border-radius: 2px;

  .list-table-head {
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

  .list-info {
    display: flex;
    padding: 20px 10px 0;
  }

  .info-prefix {
    display: inline-block;
    height: 31px;
    padding-right: 5px;
    padding-left: 5px;
    line-height: 31px;
    text-align: center;
    background: #fafbfd;
    border-right: .5px solid #c4c6cc;
    border-radius: 2px 0 0 2px;
  }

  .list-content {
    padding: 10px;

    .content-title {
      font-size: 12px;
      letter-spacing: 0;
      color: #4d4f56;
    }

    .content {
      padding-top: 10px;
    }
  }
}

.render-field {
  display: flex;
  min-width: 640px;
  overflow: hidden;

  /* border: 1px solid #dcdee5; */
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
  transition: background-color .2s;

  &:hover {
    background: #f5f7fa;
  }
}

.field-icon {
  margin-left: 20px;
  color: #c4c6cc;
  cursor: pointer;
}

.add-field {
  margin-top: 10px;
}

.plus-circle {
  font-size: 14px;
  color: #3a84ff;
  cursor: pointer;
}

.plus-circle-text {
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
}

.field-span {
  margin-left: 5px;
  color: #c4c6cc;
  cursor: pointer;
}

.underline-dashed {
  text-decoration: underline;
  text-decoration-style: dashed;
  text-decoration-color: #c4c6cc;
  text-underline-offset: 5px;
  cursor: pointer;
}

.field-value-move {
  margin-left: 5px;
  font-size: 18px;
  color: #c4c6cc;
  cursor: move;
}

.field-value-text {
  margin-left: 5px;
  color: #4d4f56;
}

.field-span-black {
  margin-left: 5px;
  color: #63656e;
  cursor: pointer;
}

.field-required-pop-hideen {
  max-height: 300px;
  overflow-y: auto;
}

.list-table-body {
  background-color: #fafbfd;
}
</style>
