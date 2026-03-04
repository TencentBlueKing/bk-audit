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
  <div class="yaml-editor">
    <div class="title">
      <span>{{ t('yaml 编辑器') }}</span>
      <span style="margin-left: auto;">
        <input
          ref="uploadRef"
          accept=".yaml"
          name="avatar"
          style="display: none;"
          type="file"
          @change="handleChangYaml">
        <audit-icon
          v-bk-tooltips="t('上传')"
          class="icon"
          type="upload"
          @click="handleUpload" />
        <audit-icon
          v-bk-tooltips="t('下载')"
          class="ml16 icon"
          type="download"
          @click="handleDownload()" />
        <audit-icon
          v-bk-tooltips="t('全屏')"
          class="ml16 icon"
          type="full-screen"
          @click.stop="handleToggleFullScreen" />
      </span>
    </div>
    <div
      ref="rootRef"
      class="yaml-container"
      :style="{height: '500px', width: '100%'}">
      <audit-icon
        v-if="showExit"
        v-bk-tooltips="t('退出全屏')"
        class="ml16 exit-icon"
        type="un-full-screen-2"
        @click="handleExitFullScreen" />
      <render-problems
        v-if="showProblems"
        :problems="problems" />
    </div>
    <span
      v-if="isError"
      class="is-error">{{ message }}</span>
  </div>
</template>
<script setup lang="ts">
  import * as monaco from 'monaco-editor';
  import screenfull from 'screenfull';
  import {
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CollectorManageService from '@service/collector-manage';

  import useRequest from '@hooks/use-request';

  import RenderProblems from './problems.vue';

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  interface Props {
    data: Record<string, any>,
    yamlData: string,
    logConfigType: string
  }
  interface Exposes {
    getCheckConfigYaml: ()=>void
  }
  interface Emits{
    (e:'update:yamlData', value: Props['yamlData']): void
    (e: 'checkYaml', value: string): void
  }
  // eslint-disable-next-line vue/no-setup-props-destructure
  const yaml = ref(props.yamlData);
  const rootRef = ref();
  const uploadRef = ref();
  const showExit = ref(false);
  const showProblems = ref(false);
  const filename = ref('');
  const problems = ref([]);
  const isError = ref(false);
  const message = ref('采集配置不能为空');
  let editor: monaco.editor.IStandaloneCodeEditor;
  const timer = ref<number| unknown>(null);


  // 实现全屏
  const handleToggleFullScreen = () => {
    handleScreenfull();
  };
  // 退出全屏
  const handleExitFullScreen = () => {
    handleScreenfull();
  };
  const handleScreenfullChanage = () => {
    if (screenfull.isFullscreen) {
      showExit.value = true;
    } else {
      showExit.value = false;
    }
    editor.layout();
  };
  screenfull.on('change', handleScreenfullChanage);
  const handleReize = () => {
    editor.layout();
  };
  const handleScreenfull = () => {
    screenfull.toggle(rootRef.value);
  };

  // 文件上传
  const handleUpload = () => {
    uploadRef.value.click();
  };
  const handleChangYaml = (e: any) => {
    const reader = new FileReader();
    filename.value = uploadRef.value.files[0].name;
    reader.readAsText((uploadRef.value.files[0]));
    reader.onload = (e: Event) => {
      const target = e.target as FileReader;
      yaml.value = target.result as string;
      const model = monaco.editor.createModel(yaml.value, 'yaml');
      editor.setModel(model);
      emits('update:yamlData', editor.getValue());
      emits('checkYaml', editor.getValue());
    };
    e.target.value = '';
  };

  // 切换容器环境获取yaml模板 检测语法
  const {
    run: fetchConfigYaml,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.fetchConfigYaml, {
    defaultValue: {},
    defaultParams: {
      bk_biz_id: props.data.bk_biz_id,
      bcs_cluster_id: props.data.bcs_cluster_id,
      yaml_config: yaml.value,
    },
    onSuccess: (data) => {
      if (data.parse_status) {
        showProblems.value = false;
        // emits('update:yamlData', editor.getValue());
      } else {
        showProblems.value = true;
        problems.value = [];
        problems.value = data.parse_result.reduce((result: Array<string>, item: Record<string, any>) => {
          // eslint-disable-next-line no-param-reassign
          result.push(item.message);
          return result;
        }, []);
      }
    },
  });

  // 文件下载
  const handleDownload = () => {
    const link = document.createElement('a');
    link.download = filename.value;
    link.style.display = 'none';
    // 字符内容转变成blob地址
    const blob = new Blob([yaml.value], { type: 'yaml' });
    link.href = URL.createObjectURL(blob);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  watch(() => props.yamlData, (yamlData) => {
    yaml.value = yamlData;
    const model = monaco.editor.createModel(yaml.value, 'yaml');
    editor.setModel(model);
    emits('checkYaml', yaml.value);
  }, {
    deep: true,
  });
  watch(() => props.logConfigType, (logConfigType) => {
    filename.value = `${logConfigType}.yaml`;
  }, {
    deep: true,
    immediate: true,
  });
  onMounted(() => {
    editor = monaco.editor.create(rootRef.value, {
      value: yaml.value,
      language: 'yaml',
      theme: 'vs-dark',
      minimap: {
        enabled: true,
      },
      automaticLayout: true,
      wordWrap: 'bounded',
    });
    editor.layout();
    window.addEventListener('resize', handleReize);
    editor.onDidChangeModelContent(() => { // 实时校验yaml语法
      if (timer.value) clearTimeout(timer.value as any);
      if (props.data.bk_biz_id) {
        timer.value = setTimeout(() => {
          timer.value = null;
          emits('checkYaml', editor.getValue());
        }, 500);
      }
    });
    editor.onDidBlurEditorText(() => {
      emits('update:yamlData', editor.getValue());
    });
  });

  onBeforeUnmount(() => {
    editor.dispose();
    screenfull.off('change', handleScreenfullChanage);
    window.removeEventListener('resize', handleReize);
  });

  defineExpose<Exposes>({
    getCheckConfigYaml() {
      const yaml = editor.getValue();
      if (!yaml) {
        // emits('update:yamlData', yaml);
        isError.value = true;
        message.value = t('采集配置不能为空');
        return false;
      }
      if (props.data.bk_biz_id && props.data.bcs_cluster_id) {
        return fetchConfigYaml({
          bk_biz_id: props.data.bk_biz_id,
          bcs_cluster_id: props.data.bcs_cluster_id,
          yaml_config: btoa(unescape(encodeURIComponent(yaml))),
        }).then((res) => {
          // emits('update:yamlData', yaml);
          if (res.parse_status) {
            isError.value = false;
            return true;
          }
          isError.value = true;
          message.value = props.data.yaml_config === yaml ? t('yaml配置错误') : t('yaml语法错误');
          return false;
        });
      }
      isError.value = false;
      return true;
    },
  });


</script>
<style lang="postcss">
.yaml-editor {
  width: 95%;
  min-width: 800px;
  line-height: 40px;

  .title {
    display: flex;
    height: 40px;
    padding: 0 25px;
    font-size: 14px;
    color: #c4c6cc;
    background: #2e2e2e;
    box-shadow: 0 2px 4px 0 rgb(0 0 0 / 16%);

    .icon {
      font-size: 16px;
      cursor: pointer;
    }
  }

  .yaml-container {
    position: relative;
  }

  .exit-icon {
    position: absolute;
    top: 10px;
    right: 20px;
    z-index: 11111;
    font-size: 20px;
    color: white;
    cursor: pointer;
  }

  .is-error {
    color: #ea3636;
  }
}

.yaml-editor + .bk-form-error {
  display: none !important;
}
</style>
