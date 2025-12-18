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
    ref="rootRef"
    class="log-container" />
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import * as monaco from 'monaco-editor';
  import {
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';

  interface Props{
    data: any;
    descriptions: {
      [k:string]: string
    };
    theme: string;
  }

  interface Exposes {
    getValue: () => string;
  }
  const props = defineProps<Props>();

  const rootRef = ref();
  const copyJson = ref();

  let editor: monaco.editor.IStandaloneCodeEditor;

  watch(() => props.theme, (theme) => {
    monaco.editor.setTheme(theme);
  });

  watch(() => [props.data, props.descriptions], (data) => {
    const [logData, descriptions] = data;
    setTimeout(() => {
      try {
        let jsonData: { [x: string]: any; };
        if (_.isPlainObject(logData)) {
          jsonData = logData;
        } else {
          jsonData = JSON.parse(logData);
          if (!_.isPlainObject(jsonData)) {
            return {};
          }
        }
        copyJson.value = JSON.stringify(jsonData, null, 2);
        // 处理json数据
        const log = Object.keys(jsonData).reduce((result, item) => {
          let jsonItem = '';
          const description = descriptions[item] ? `// ${descriptions[item]}` : '';
          if (!_.isPlainObject(jsonData[item])) {
            jsonItem = `"${item}":${JSON.stringify(jsonData[item], null, 4)},`;
          } else {
            const jsonObjItem = handleJsonItem(jsonData[item], item);
            jsonItem += `"${item}": { ${description}\n${jsonObjItem}  },`;
          }
          const jsonObjItem = _.isPlainObject(jsonData[item]) ? `${jsonItem}` : `${jsonItem} ${description}`; // 对象注释拼在前面
          // eslint-disable-next-line no-param-reassign
          result += `  ${jsonObjItem}\n`;
          return result;
        }, '');
        const model = monaco.editor.createModel(`{\n${log}}`, 'json');
        editor.setModel(model);
      } catch {
        const model = monaco.editor.createModel(logData, '');
        editor.setModel(model);
      }
      editor.layout();
    });
  }, {
    immediate: true,
  });
  const handleReize = () => {
    editor.layout();
  };
  // 单独处理日志对象
  const handleJsonItem = (json: Record<string, any>, item: string, tab?: boolean) => {
    const jsonObjItem = Object.keys(json).reduce((result, objItem) => {
      let jsonItem = '';
      if (!_.isObject(json[objItem])) {
        if (tab) {
          jsonItem = `  "${objItem}":${JSON.stringify(json[objItem])},`;
        } else {
          jsonItem = `"${objItem}":${JSON.stringify(json[objItem])},`;
        }
      } else {
        if (_.isArray(json[objItem])) {
          const arrayItem = json[objItem].reduce((res: string, arrayItem:any) => {
            const arrayJsonItem = handleJsonItem(arrayItem, '');
            if (!_.isObject(arrayItem)) {
              // eslint-disable-next-line no-param-reassign
              res += `      "${arrayItem}",\n`;
            } else if (_.isArray(arrayItem)) {
              // eslint-disable-next-line no-param-reassign
              res += `    [\n${arrayJsonItem}    ],\n`;
            } else if (_.isObject(arrayItem)) {
              // eslint-disable-next-line no-param-reassign
              res += `    {\n${arrayJsonItem}    },\n`;
            }

            return res;
          }, '');
          jsonItem += `"${objItem}": [\n${arrayItem}    ],`;
        } else {
          const listItem = handleJsonItem(json[objItem], objItem, true);
          jsonItem += `"${objItem}": {\n${listItem}    },`;
        }
      }
      // eslint-disable-next-line no-param-reassign
      result += `    ${jsonItem}\n`;
      return result;
    }, '');
    return jsonObjItem;
  };
  onMounted(() => {
    editor = monaco.editor.create(rootRef.value, {
      language: 'json',
      theme: props.theme,
      readOnly: true,
      minimap: {
        enabled: false,
      },
      wordWrap: 'bounded',
    });
    window.addEventListener('resize', handleReize);
  });

  onBeforeUnmount(() => {
    editor.dispose();
    window.removeEventListener('resize', handleReize);
  });

  defineExpose<Exposes>({
    getValue() {
      return copyJson.value;
    },
  });
</script>
<style lang="postcss" scoped>
  .log-container {
    width: 640px;
    height: calc(100vh - 60px);
  }
</style>
