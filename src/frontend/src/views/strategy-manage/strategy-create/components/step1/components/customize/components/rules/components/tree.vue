<template>
  <bk-select ref="selectRef" v-model="selectedValue" :auto-height="false" collapse-tags custom-content @search-change="handleSearch"
    :popoverOptions="{ 'width': 'auto' }" display-key="name" id-key="id" multiple>
    <bk-tree ref="treeRef" children="children" :data="treeData" empty-text=" " label="raw_name"
      :node-content-action="['click']" :show-node-type-icon="false" @node-checked="handleNodeChecked"
      @nodeClick="handleNodeClick">
      <template #default="{ data }">
        <div class="field" v-if="!(data.isEdit)">
          <div class="field-left">
            <audit-icon style="margin-right: 4px;font-size: 14px;" svg :type="data.spec_field_type" />
            <span v-if="props.configType === 'LinkTable'">
              <span style=" color: #3a84ff;">{{ data.table }}.</span>
              <span class="field-type-span">{{ getAggregateName(data) }}{{ data.display_name }}{{ data.raw_name ?
                `(${data.raw_name})` : ``
                }}
                <span v-for="(field, fieldIndex) in data?.fieldTypeValueAr" :key="fieldIndex">
                  <span class="subscript">/</span>
                  {{ field }}
                </span>
              </span>
            </span>
            <span v-else>
              <span class="field-type-span">{{ getAggregateName(data) }}{{ data.display_name }}{{ data.raw_name ?
                `(${data.raw_name})` : ``
                }}
                <span v-for="(field, fieldIndex) in data?.fieldTypeValueAr" :key="fieldIndex">
                  <span class="subscript">/</span>
                  {{ field }}
                </span>
              </span>
            </span>
          </div>
          <div class="field-right"
            v-if="data.spec_field_type === 'object' && ('dynamic_content' in data.property) && data.property.dynamic_content">
            <audit-icon @click.stop="handleAddNode(data)" style="margin-right: 4px;font-size: 14px;color: #3a84ff;" svg
              type="plus-circle" />
            <bk-popover width="300" placement="right" theme="light">
              <template #content>
                <div>
                  <p>如果你对字段有多级下钻的需求，请注意：{{ data.spec_field_type }}</p>
                  <p>1.点击 “ + ”表示新增一级下钻 </p>
                  <p>2.在请输入的输入框内，直接填写字段名 </p>
                  <p>3.可通过多次添加来实现多级下钻，请严格注意字段级别 </p>
                  <br />
                  <p>以下是3级字段的实列 </p>
                  <p>
                    <audit-icon style="margin-top: 6px;margin-right: 4px;font-size: 14px;" svg type="string" />
                    <span style=" color: #3a84ff;">b.</span>
                    <span> one</span>
                    <span class="field-type-span">/</span>
                    <span>two</span>
                    <span class="field-type-span">/</span>
                    <span>three</span>
                  </p>
                </div>
              </template>
              <audit-icon style="margin-right: 4px;font-size: 14px;color: #3a84ff;" svg type="help-fill" />
            </bk-popover>
          </div>
        </div>
        <div v-else>
          <div class="field-edit">
            <div class="field-edit-left">
              <div class="field-type" v-if="data.spec_field_type !== ''">
                <audit-icon style="margin-right: 4px;font-size: 14px;" svg :type="data.spec_field_type" />
                <span v-if="props.configType === 'LinkTable'">
                  <span style=" color: #3a84ff;">{{ data.parent_table }}.</span>
                  <span class="field-type-span">{{ getAggregateName(data) }}{{ data.parent_raw_name ?
                    `(${data.parent_raw_name})` : `` }}</span>
                  <span class="field-type-span">/</span>
                </span>
                <span v-else>
                  <span class="field-type-span">{{ getAggregateName(data) }}{{ data.parent_raw_name }}</span>
                </span>
              </div>

              <bk-select v-else v-model="data.spec_field_type" size="small" empty-text="请选择字段类型" :filterable="false"
                :popoverOptions="{ 'boundary': 'parent' }" style="width: 200px;"
                @select="handleSelect(data)">
                <bk-option v-for="item in fieldTypeList" :id="item.id" :key="item.id"
                  :name="`${item.name}(${item.id})`" />
              </bk-select>
              <div v-if="data.spec_field_type !== ''">
                <span v-for="(subItem, index) in fieldTypeValue[data.parent_raw_name]" :key="subItem.id">
                  <span class="field-type-span subscript">/</span>
                  <bk-input v-model="subItem[`field_value_${index}`]" class="edit-input" size="small" />
                </span>

                <audit-icon @click.stop="handleAddField(data)" style="margin-left: 4px;font-size: 14px;color:#c4c6cc;"
                  svg type="add-fill" />
              </div>
            </div>
            <div class="field-edit-right edit-icon">
              <audit-icon v-if="data.spec_field_type !== ''" style="margin-right: 4px;font-size: 18px;color:#7bbe8a;"
                svg type="check-line" @click.stop="handleAddFieldSubmit(data)" />
              <audit-icon style="margin-right: 4px;font-size: 18px;color:#c1c3c9;" svg type="close" @click.stop="handleAddFieldClose(data)"/>
            </div>
          </div>
        </div>
      </template>
    </bk-tree>
  </bk-select>
</template>
<script setup lang="tsx">
import { computed, ref, watch, onMounted } from 'vue';
import DatabaseTableFieldModel from '@model/strategy/database-table-field';
import MetaManageService from '@service/meta-manage';
import useRequest from '@hooks/use-request';


  interface Emits {
    (e: 'handleNodeSelectedValue', node: any, value: string ): void;
  }
interface Props {
  configData: any[],
  configType: string,
  aggregateList: Array<Record<string, any>>,
}
const props = defineProps<Props>();
const emits = defineEmits<Emits>();

const fieldTypeValue = ref<Record<string, Record<string, any>[]>>({});


const fieldTypeList = ref<{ id: string; name: string }[]>([]);

const treeData = ref<Record<string, any>[]>([]);
const storageTreeData = ref<Record<string, any>[]>([]);
const newItem = {
  aggregate: null,
  parent_aggregate: null,
  children: [],
  selectedValue:"",
  display_name: "",
  parent_display_name: "",
  field_type: "",
  isEdit: true,
  parent_raw_name: "",
  raw_name: "",
  remark: "",
  spec_field_type: "",
  parent_table: "",
  table: "",
};
const handleSelect = (val: Record<string, any>) =>{
  val.field_type = val.spec_field_type
}
const nodeInput = ref('');
const treeRef = ref();
const selectedValue = ref();
const selectRef = ref(null);
// 取消
const handleAddFieldClose = (val: Record<string, any>) => {
  treeData.value.forEach((node: Record<string, any>) => {
    if (node.raw_name === val.parent_raw_name) {
      node.children.pop();
    }
  });
  storageTreeData.value = treeData.value
};
// 搜索逻辑
const handleSearch = (keyword: string) => {
  if (!keyword) {
    treeData.value =  storageTreeData.value
    return;
  }

  const matchedNodes = searchTreeNodes(treeData.value, keyword);
};


const searchTreeNodes = (nodes:Record<string, any> , keyword: string) => {  
  const matchedNodes: Record<string, any>[] = []; // 使用 Record<string, any>[]

  nodes.forEach((node: Record<string, any>)=> {
    if (node.display_name.includes(keyword) || node.raw_name.includes(keyword)) {
      matchedNodes.push(node);
    }
    if (node.children && node.children.length > 0) {
      matchedNodes.push(...searchTreeNodes(node.children, keyword));
    }
  });
  treeData.value  = matchedNodes;
  return matchedNodes;
}
// 添加子项目
const handleAddNode = (val: Record<string, any>) => {
  const findAndInsert = (nodes: Array<Record<string, any>>) => {
    for (const node of nodes) {
      if (node.raw_name === val.raw_name) {
        // 检查是否已经存在具有相同 id 的子项（根据需求调整）
        const alreadyExists = node.children.some((child: Record<string, any>) => child.raw_name === newItem.raw_name);
        if (!alreadyExists) {
          newItem.parent_display_name = val.display_name
          newItem.parent_aggregate = val.aggregate
          newItem.parent_raw_name = val.raw_name
          newItem.parent_table = val.table
          newItem.table = val.table
          fieldTypeValue.value[val.raw_name] = [{
            id: 0,
            field_value_0: ''
          }]
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
  fieldTypeValue.value[val.parent_raw_name].push({
    id: fieldTypeValue.value[val.parent_raw_name].length,
    [`field_value_${fieldTypeValue.value[val.parent_raw_name].length}`]: ''
  })
}
// 确定添加
const handleAddFieldSubmit = (val: Record<string, any>) => {
  const fieldTypeValueAr = fieldTypeValue.value[val.parent_raw_name].map((item: Record<string, any>) => {
    return item[`field_value_${item.id}`]
  })
  const fieldTypeValueText = fieldTypeValueAr.join('_')
  treeData.value.forEach((node: Record<string, any>) => {
    if (node.raw_name === val.parent_raw_name) {
      node.children.forEach((e: Record<string, any> )=> {
        if (e.isEdit) {
          e.isEdit = false
          e.display_name = e.parent_display_name
          e.raw_name = e.parent_raw_name
          e.fieldTypeValueAr = fieldTypeValueAr
          e.selectedValue = `${e.parent_display_name}(${e.parent_raw_name}_${fieldTypeValueText})`
        }
      });
       
    }
  })
  storageTreeData.value = treeData.value
}
// 选择
const handleNodeClick = (nodes: Record<string, any>) => {
  selectedValue.value = nodes.selectedValue;
  emits('handleNodeSelectedValue', nodes, nodes.selectedValue);
};

const handleNodeChecked = (nodes: Record<string, any>) => {
};

const getAggregateName = (element: Record<string, any>) => {  
  // 添加的子项
  if ('parent_aggregate' in element) {
    if (!element.parent_aggregate) return '';
    const item = props.aggregateList.find(item => item.value === element.parent_aggregate);
    return `[${item?.label}]`;
  } else {
    if (!element.aggregate) return '';
    const item = props.aggregateList.find(item => item.value === element.aggregate);
    return `[${item?.label}]`;
  }
};

// 获取字段类型
const {
  run: fetchGlobalChoices,
} = useRequest(MetaManageService.fetchGlobalChoices, {
  defaultValue: {},
  onSuccess(result) {
    fieldTypeList.value = result.core_sql_field_type
  },
});

const transformData = (data: any[]): Array<Record<string, any>> => {
  return data.map((item: Record<string, any> )=> {
    // 如果有子节点（sub_keys），则递归处理
    if (item.property && item.property.sub_keys && item.property.sub_keys.length > 0) {
      return {
        ...item,
        selectedValue: ('alias' in item) ?  '' : `${item.display_name}(${item.raw_name})` ,
        children: transformData(item.property.sub_keys), // 递归处理子节点
        display_name: ('alias' in item) ? item.label : item.display_name, // 使用原始数据的 label 作为树节点的显示名称
        raw_name: ('alias' in item) ? item.value : item.raw_name     // 唯一标识符（根据你的需求可以是 value 或其他字段）
      };
    } else {
      return {
        ...item,
        selectedValue:  ('alias' in item) ? '' : `${item.display_name}(${item.raw_name})` ,
        children: [],
        display_name: ('alias' in item) ? item.label : item.display_name, // 使用原始数据的 label 作为树节点的显示名称
        raw_name: ('alias' in item) ? item.value : item.raw_name     // 唯一标识符（根据你的需求可以是 value 或其他字段）
      };
    }
  });
}
// 改造数据
watch(() => props, (newData) => {
  const initTreeData = JSON.parse(JSON.stringify(newData.configData))
  treeData.value = transformData(initTreeData)
  storageTreeData.value = transformData(initTreeData)
  console.log('storageTreeData.value', storageTreeData.value);
  
}, {
  deep: true,
  immediate: true,
})
onMounted(() => {
  fetchGlobalChoices()
})
</script>
<style scoped lang="postcss">
.field {
  display: flex;
  width: 100%;
  justify-content: space-between;
  padding-right: 10px;
  .field-left {
    .field-type-span {
      color: #63656e;
      text-align: center;
      font-size: 12px;
    }
  }

  .field-right {
    margin-left: 10px;
    margin-top: 3px;

  }

  .field-type-span {
    color: #49bb07;
    text-align: center;
    font-size: 12px;
  }
}

.field:hover {
  background-color: #f5f7fa;
}

.field-edit {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;

  :hover {
    background-color: #ffffff;
  }

  .field-edit-left {
    display: flex;

    .field-type {
      .field-type-span {
        color: #63656e;
        text-align: center;
        font-size: 12px;
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
  margin-left: 5px;
  margin-right: 5px;
  display: inline-block;
  height: 28px;
  width: 10px;
  padding-bottom: 2px;
  background-color: #e3ecfd;
  border-radius: 2px;
}
</style>
