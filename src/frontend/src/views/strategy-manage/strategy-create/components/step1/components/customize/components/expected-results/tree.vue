<template>
  <bk-tree
    ref="treeRef"
    children="children"
    :data="treeData"
    empty-text=" "
    label="raw_name"
    :show-node-type-icon="false">
    <template #default="{ data }">
      <div
        v-if="data"
        class="node">
        <bk-checkbox
          v-if="Object.keys(checkBoxMode).length > 0"
          v-model="checkBoxMode[data.check_box_mode_name]"
          :disabled="data.isEdit"
          :immediate-emit-change="false"
          style="width: 20px;"
          @change="(val: any) => handleChangeBox(val, data)" />
        <div
          v-if="!data.isEdit"
          class="field">
          <div class="field-left">
            <audit-icon
              style="margin-right: 4px; font-size: 14px"
              svg
              :type="data.spec_field_type" />
            <span v-if="props.configType === 'LinkTable'">
              <span style="color: #3a84ff">{{ data.table }}.</span>
              <span class="field-type-span">{{ data.display_name
                                            }}{{ data.raw_name ? `(${data.raw_name})` : `` }}
                <span
                  v-for="(field, fieldIndex) in data?.fieldTypeValueAr"
                  :key="fieldIndex">
                  <span class="subscript">/</span>
                  {{ field }}
                </span>
              </span>
            </span>
            <span v-else>
              <span
                v-if="`self_name` in data"
                class="field-type-span">
                {{ data.self_name }}
                <span class="subscript">/</span>
                {{ data.self_key_name }}
              </span>
              <span
                v-else
                class="field-type-span">
                <span v-if="`parent_raw_name` in data">{{ data.parent_display_name
                }}{{ data.parent_raw_name ? `(${data.parent_raw_name})` : `` }}</span>
                <span v-else> {{ data.display_name
                }}{{ `(${data.raw_name})` }}</span>
                <span
                  v-for="(field, fieldIndex) in data?.keys"
                  :key="fieldIndex">
                  <span class="subscript">/</span>
                  {{ field }}
                </span>
              </span>
            </span>
          </div>
          <div
            v-if="
              data.spec_field_type === 'object' &&
                'dynamic_content' in data.property &&
                data.property.dynamic_content
            "
            class="field-right">
            <bk-popover
              placement="right"
              theme="light"
              width="300">
              <template #content>
                <div>
                  <h3>{{ t('手动添加下级字段') }}</h3>
                  <p>{{ t('如果你对字段有多级下钻的需求，请注意') }}：</p>
                  <p>{{ t('1.点击 “ + ”表示新增一级下钻') }} </p>
                  <p>{{ t('2.在请输入的输入框内，直接填写字段名') }} </p>
                  <p>{{ t('3.可通过多次添加来实现多级下钻，请严格注意字段级别') }} </p>
                  <br>
                  <p>{{ t('以下是3级字段的实例') }}:</p>
                  <p>
                    <audit-icon
                      style="margin-top: 6px; margin-right: 4px; font-size: 14px"
                      svg
                      type="string" />
                    <span style="color: #3a84ff">b.</span>
                    <span> one</span>
                    <span class="field-type-span">/</span>
                    <span>two</span>
                    <span class="field-type-span">/</span>
                    <span>three</span>
                  </p>
                </div>
              </template>
              <audit-icon
                style="margin-right: 4px; font-size: 14px; color: #3a84ff"
                svg
                type="plus-circle"
                @click.stop="handleAddNode(data)" />
            </bk-popover>
          </div>
        </div>
        <div v-else>
          <div class="field-edit">
            <div class="field-edit-left">
              <div
                v-if="data.spec_field_type !== ''"
                class="field-type">
                <audit-icon
                  style="margin-right: 4px; font-size: 14px"
                  svg
                  :type="data.spec_field_type" />
                <span v-if="props.configType === 'LinkTable'">
                  <span style=" color: #3a84ff;">{{ data.parent_table }}.</span>
                  <span class="field-type-span">{{ data.parent_raw_name ?
                    `${data.parent_display_name}(${data.parent_raw_name})` : `` }}</span>
                  <span class="field-type-span">/</span>
                </span>
                <span v-else>
                  <span class="field-type-span">{{ data.parent_raw_name ?
                    `${data.parent_display_name}(${data.parent_raw_name})` : `` }}</span>
                </span>
              </div>

              <bk-select
                v-else
                v-model="data.spec_field_type"
                empty-text="请选择字段类型"
                :filterable="false"
                :popover-options="{ boundary: 'parent' }"
                size="small"
                style="width: 200px"
                @select="handleSelect(data)">
                <bk-option
                  v-for="item in fieldTypeList"
                  :id="item.id"
                  :key="item.id"
                  :name="`${item.name}(${item.id})`" />
              </bk-select>
              <div v-if="data.spec_field_type !== ''">
                <span
                  v-for="(subItem, index) in fieldTypeValue[data.parent_raw_name]"
                  :key="subItem.id">
                  <span class="field-type-span subscript">/</span>
                  <bk-input
                    v-model="subItem[`field_value_${index}`]"
                    class="edit-input"
                    :placeholder="`请输入${index+2}级字段`"
                    size="small"
                    @enter="handleAddFieldSubmit(data)" />
                </span>

                <audit-icon
                  v-bk-tooltips="{ content: '添加下级字段', placement: 'top' }"
                  style="margin-left: 4px; font-size: 14px; color: #c4c6cc"
                  svg
                  type="add-fill"
                  @click.stop="handleAddField(data)" />
              </div>
            </div>
            <div class="field-edit-right edit-icon">
              <audit-icon
                v-if="data.spec_field_type !== ''"
                v-bk-tooltips="{ content: '确认', placement: 'top' }"
                style="margin-right: 4px; font-size: 18px; color: #7bbe8a"
                svg
                type="check-line"
                @click.stop="handleAddFieldSubmit(data)" />
              <audit-icon
                v-bk-tooltips="{ content: '取消添加', placement: 'top' }"
                style="margin-right: 4px; font-size: 18px; color: #c1c3c9"
                svg
                type="close"
                @click.stop="handleAddFieldClose(data)" />
            </div>
          </div>
        </div>
      </div>
    </template>
  </bk-tree>
</template>

<script setup lang="tsx">
  import { onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { onBeforeRouteLeave, useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  interface Emits {
    (e: 'handleNodeChecked', node: any): void;
    (e: 'saveStorageTreeData', node: any): void;
  }
  interface Props {
    configData: any[];
    configType: string;
    expectedResultList: any[];
    searchKey: string;
  }
  interface Expose {
    handleSearch: (val: string) => void,
  }
  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const checkBoxMode = ref<Record<string, boolean>>({});
  const route = useRoute();
  const fieldTypeValue = ref<Record<string, Record<string, any>[]>>({});

  const fieldTypeList = ref<{ id: string; name: string }[]>([]);
  const changeBoxData = ref<Record<string, any>[]>([]);

  const treeData = ref<Record<string, any>[]>([]);
  const storageTreeData = ref<Record<string, any>[]>([]);
  const newItem = {
    aggregate: null,
    aggregateList: [],
    parent_aggregate: null,
    children: [],
    check_box_mode_name: '',
    display_name: '',
    keys: [],
    is_checked: false,
    parent_display_name: '',
    field_type: '',
    isEdit: true,
    isOpen: false,
    parent_raw_name: '',
    raw_name: '',
    remark: '',
    spec_field_type: '',
    parent_table: '',
    table: '',
    isDuplicate: false,
    c: false,
  };
  const treeRef = ref();
  const handleSelect = (val: Record<string, any>) => {
    // eslint-disable-next-line no-param-reassign
    val.field_type = val.spec_field_type;
  };

  // 添加子项目
  const handleAddNode = (val: Record<string, any>) => {
    const findAndInsert = (nodes: Array<any>) => {
      for (const node of nodes) {
        if (node.raw_name === val.raw_name) {
          // 检查是否已经存在具有相同 id 的子项（根据需求调整）
          const alreadyExists = node.children.some((child: Record<string, any>) => child.raw_name === newItem.raw_name);
          if (!alreadyExists) {
            newItem.parent_display_name = val.display_name;
            newItem.parent_aggregate = val.aggregate;
            newItem.parent_raw_name = val.raw_name;
            newItem.aggregateList = val.aggregateList;
            newItem.parent_table = val.table;
            newItem.field_type = val.field_type;
            newItem.isDuplicate = val.isDuplicate;
            newItem.table = val.table;
            newItem.is_checked = false;
            fieldTypeValue.value[val.raw_name] = [
              {
                id: 0,
                field_value_0: '',
              },
            ];
            node.children.push({ ...newItem });
            node.isOpen = true; // 打开
          }

          return; // 找到并插入后退出循环
        }

        if (node.children && node.children.length > 0) {
          findAndInsert(node.children);
        }
      }
    };

    findAndInsert(treeData.value);
  };
  // 子项添加
  const handleAddField = (val: Record<string, any>) => {
    const hasEmptyValue = fieldTypeValue.value[val.parent_raw_name].some((item: Record<string, any>) => {
      const fieldKey = `field_value_${item.id}`;
      return !item[fieldKey] || item[fieldKey].trim() === '';
    });
    if (hasEmptyValue) {
      return;
    }
    fieldTypeValue.value[val.parent_raw_name].push({
      id: fieldTypeValue.value[val.parent_raw_name].length,
      [`field_value_${fieldTypeValue.value[val.parent_raw_name].length}`]: '',
    });
  };
  // 确定添加
  const handleAddFieldSubmit = (val: Record<string, any>) => {
    const fieldTypeValueAr = fieldTypeValue.value[val.parent_raw_name].map(item => item[`field_value_${item.id}`]);
    const hasEmptyValue = fieldTypeValue.value[val.parent_raw_name].some((item: Record<string, any>) => {
      const fieldKey = `field_value_${item.id}`;
      return !item[fieldKey] || item[fieldKey].trim() === '';
    });
    if (hasEmptyValue) {
      return;
    }
    const fieldTypeValueText = fieldTypeValueAr.join('/');
    treeData.value.forEach((node: Record<string, any>) => {
      if (node.raw_name === val.parent_raw_name) {
        node.children.forEach((e: Record<string, any>) => {
          if (e.isEdit) {
            e.isEdit = false;
            e.display_name = e.parent_display_name;
            e.textValue = `${e.parent_display_name}(${e.parent_raw_name})/${fieldTypeValueText}`;
            e.raw_name = e.parent_raw_name;
            e.keys = fieldTypeValueAr;
            // eslint-disable-next-line no-param-reassign
            node.isOpen = true;
            e.is_checked = false;
            e.fieldTypeValueAr = fieldTypeValueAr;
            e.check_box_mode_name = `${e.raw_name}-${e.parent_display_name}(${e.parent_raw_name})/${fieldTypeValueText}`;
          }
        });
      }
    });
    storageTreeData.value = treeData.value;
  };
  // 取消
  const handleAddFieldClose = (val: Record<string, any>) => {
    treeData.value.forEach((node: Record<string, any>) => {
      if (node.raw_name === val.parent_raw_name) {
        node.children.pop();
      }
    });
    storageTreeData.value = treeData.value;
  };

  const handleNodeChecked = (nodes: Record<string, any>) => {
    emits('handleNodeChecked', nodes);
  };

  // 获取字段类型
  const { run: fetchGlobalChoices } = useRequest(
    MetaManageService.fetchGlobalChoices,
    {
      defaultValue: {},
      onSuccess(result) {
        fieldTypeList.value = result.core_sql_field_type;
      },
    },
  );
  const handleChangeBox = (val: boolean, data: Record<string, any>) => {
    if (val) {
      // 检查是否已存在相同的data
      // eslint-disable-next-line max-len
      const isDuplicate = changeBoxData.value.some(item => (item.raw_name === data.raw_name) && (item.display_name === data.display_name));
      if (!isDuplicate) {
        changeBoxData.value.push(data);
      }
    } else {
      // 如果val为false，从changeBoxData中删除对应的data
      // eslint-disable-next-line max-len
      const index = changeBoxData.value.findIndex(item => (item.raw_name === data.raw_name) && (item.display_name === data.display_name));
      if (index !== -1) {
        changeBoxData.value.splice(index, 1);
      }
    }
  };
  const transformData = (data: any[]): Array<Record<string, any>> => data.map((item: Record<string, any>) => {
    // 如果有子节点（sub_keys），则递归处理
    if (
      item.property
      && item.property.sub_keys
      && item.property.sub_keys.length > 0
    ) {
      // 递归处理子节点，并确保子节点继承父级的 table
      return {
        ...item,
        is_checked: false,
        children: transformData(item.property.sub_keys).map(child => ({
          ...child,
          self_name: `${item.display_name}(${item.raw_name})`,
          self_key_name: `${child.alias}(${child.value})`,
          table: child.table || item.table,
          raw_name: child.raw_name || item.raw_name,
          is_checked: false,
        })),
        keys: 'alias' in item ? [item.value] : [],
        display_name: 'alias' in item ? item.label : item.display_name,
        raw_name: item.raw_name,
        check_box_mode_name: `${item.raw_name}-${item.display_name}`,
      };
    }
    return {
      ...item,
      children: [],
      keys: 'alias' in item ? [item.value] : [],
      display_name: 'alias' in item ? item.label : item.display_name,
      raw_name: item.raw_name,
      is_checked: false,
      check_box_mode_name: 'alias' in item ? `${item.value}_${item.label}` : `${item.raw_name}-${item.display_name}`,
    };
  });


  // 改造数据
  watch(
    () => props,
    (newData) => {
      checkBoxMode.value = {};
      const haveTreeData = sessionStorage.getItem('storage-tree-data');
      if (haveTreeData) {
        treeData.value = JSON.parse(sessionStorage.getItem('storage-tree-data') || '[]');
      } else {
        const initTreeData = JSON.parse(JSON.stringify(newData.configData));
        if (route.name === 'strategyEdit') {
          // 编辑时手动插入数据回显
          const initData = transformData(initTreeData);
          newData.expectedResultList.forEach((e) => {
            initData.forEach((item) => {
              if ('keys' in e && e?.keys.length >= 1 && (e.raw_name === item.raw_name)) {
                const addItem = JSON.parse(JSON.stringify(newItem));
                addItem.parent_display_name = item.display_name;
                addItem.parent_aggregate = item.aggregate;
                addItem.parent_raw_name = item.raw_name;
                addItem.aggregateList = item.aggregateList;
                addItem.parent_table = item.table;
                addItem.field_type = item.field_type;
                addItem.isDuplicate = item.isDuplicate;
                addItem.isOpen = false;
                addItem.isEdit = false;
                addItem.table = item.table;
                addItem.spec_field_type = item.field_type;
                addItem.check_box_mode_name = `${e.raw_name}-${e.display_name}-${e.keys.join('/')}`;
                item.children.push({ ...addItem, ...e });
              }
            });
          });
          treeData.value = initData;
          storageTreeData.value = initData;
        } else {
          treeData.value = transformData(initTreeData);
          storageTreeData.value = transformData(treeData.value);
        }
      }
      // 遍历treeData.value并为每个节点添加checkBoxMode属性
      const traverseAndSetCheckboxMode = (nodes: any[]) => {
        nodes.forEach((node) => {
          checkBoxMode.value[node.check_box_mode_name] =  false;
          if (node.children && node.children.length > 0) {
            traverseAndSetCheckboxMode(node.children);
          }
        });
      };
      traverseAndSetCheckboxMode(treeData.value);
    },
    {
      deep: true,
      immediate: true,
    },
  );

  watch(
    () => changeBoxData.value,
    (newData) => {
      handleNodeChecked(newData);
    },
    {
      deep: true,
    },
  );
  watch(
    () => storageTreeData.value,
    (newData) => {
      sessionStorage.setItem('storage-tree-data', JSON.stringify(newData));
    },
    {
      deep: true,
    },
  );

  defineExpose<Expose>({
    handleSearch: (val: string) => {
      // eslint-disable-next-line max-len
      const searchInTree = (nodes: Record<string, any>) => nodes.reduce((result: Record<string, any>, node: Record<string, any>) => {
        // 检查当前节点
        if (node.raw_name.includes(val) || node.display_name.includes(val)) {
          result.push(node);
        }

        // 如果有子节点，递归搜索
        if (node.children && node.children.length > 0) {
          result.push(...searchInTree(node.children));
        }

        return result;
      }, []);
      treeData.value = searchInTree(storageTreeData.value);
    },
  });
  onMounted(() => {
    fetchGlobalChoices();
  });
  onBeforeRouteLeave((to, from, next) => {
    sessionStorage.removeItem('storage-tree-data'); // 清除数据
    next();
  });
</script>
<style scoped lang="postcss">
.node {
  display: flex;

  .field {
    display: flex;
    width: 100%;
    justify-content: space-between;
    padding-right: 10px;

    .field-left {
      .field-type-span {
        font-size: 12px;
        color: #63656e;
        text-align: center;
      }
    }

    .field-right {
      margin-top: 3px;
      margin-left: 10px;
    }

    .field-type-span {
      font-size: 12px;
      color: #49bb07;
      text-align: center;
    }
  }

}

.node:hover {
  background-color: #f5f7fa;
}

.field-edit {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;

  :hover {
    background-color: #fff;
  }

  .field-edit-left {
    display: flex;

    .field-type {
      .field-type-span {
        font-size: 12px;
        color: #63656e;
        text-align: center;
      }
    }

    .edit-input {
      width: 100px;
      margin-left: 5px;
    }
  }
}

.field-edit>* {
  margin: 0;

  /* 确保没有额外的外边距影响布局 */
}

.subscript {
  display: inline-block;
  width: 10px;
  height: 28px;
  padding-bottom: 2px;
  margin-right: 5px;
  margin-left: 5px;
  background-color: #e3ecfd;
  border-radius: 2px;
}
</style>
