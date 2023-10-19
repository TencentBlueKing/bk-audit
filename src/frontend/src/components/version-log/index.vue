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
  <bk-dialog
    dialog-type="show"
    :draggable="false"
    ext-cls="version-log-dialog"
    height="70%"
    :is-show="isShow"
    title=""
    width="60%"
    @value-change="handleValueChange">
    <div
      class="log-version">
      <div class="log-version-left">
        <ul class="left-list">
          <li
            v-for="(item,index) in versions.version_logs"
            :key="index"
            class="left-list-item"
            :class="{ 'item-active': index === active }"
            @click="handleItemClick(item.version, index)">
            <span class="item-title">{{ item.version }}</span>
            <span class="item-date">{{ item.release_at }}</span>
            <span
              v-if="index === current"
              class="item-current">{{ t('当前版本') }}</span>
          </li>
        </ul>
      </div>

      <div class="log-version-right">
        <bk-loading :loading="loading">
          <!-- eslint-disable vue/no-v-html -->
          <div
            class="markdowm-container"
            v-html="content" />
        </bk-loading>
      </div>
    </div>
  </bk-dialog>
</template>
<script  setup lang="ts">
  import {
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import VersionManageService from '@service/version-manage';

  import VersionsModel from '@model/version/versions';

  import useRequest from '@hooks/use-request';

  interface Props {
    isShow: boolean
  }
  interface Emits {
    (e: 'update:isShow', value: boolean): void,
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const current = ref(0);
  const active = ref(0);
  const handleValueChange = (value: boolean) => {
    emits('update:isShow', value);
  };
  const handleItemClick = (version: string, index: number) => {
    active.value = index;
    fetchVersionContent({
      version,
    });
  };
  const {
    data: versions,
    run: fetchVersions,
  } = useRequest(VersionManageService.fetchVersions, {
    defaultValue: new VersionsModel(),
    manual: true,
    onSuccess: (result) => {
      if (result.show_version) {
        emits('update:isShow', result.show_version);
      }
      if (result.version_logs.length) {
        fetchVersionContent({
          version: result.version_logs[0].version,
        });
      }
    },
  });

  const {
    loading,
    data: content,
    run: fetchVersionContent,
  } = useRequest(VersionManageService.fetchVersionContent, {
    defaultValue: '',
  });

  watch(() => props.isShow, () => {
    if (props.isShow) {
      fetchVersions();
    }
  });
</script>

<style lang="postcss">
.log-version {
  display: flex;
  margin: -33px -24px -26px;

  .log-version-left {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 200px;
    padding: 40px 0;
    overflow: hidden;
    font-size: 12px;
    background-color: #fafbfd;
    border-right: 1px solid #dcdee5;

    .left-list {
      display: flex;
      width: 100%;
      height: 598px;
      overflow: auto;
      border-top: 1px solid #dcdee5;
      flex-direction: column;

      .left-list-item {
        position: relative;
        display: flex;
        padding-left: 30px;
        cursor: pointer;
        border-bottom: 1px solid #dcdee5;
        flex: 0 0 54px;
        flex-direction: column;
        justify-content: center;

        .left-list-item:hover {
          cursor: pointer;
          background-color: #fff;
        }

        .item-title {
          font-size: 16px;
          color: #313238;
        }

        .item-date {
          color: #979ba5;
        }

        .item-current {
          position: absolute;
          top: 8px;
          right: 20px;
          display: flex;
          width: 58px;
          height: 20px;
          line-height: 9px;
          color: #fff;
          background-color: #699df4;
          border-radius: 2px;
          align-items: center;
          justify-content: center;
        }
      }

      .left-list-item.item-active {
        background-color: #fff;
      }

      .left-list-item.item-active::before {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        width: 6px;
        background-color: #3a84ff;
        content: " ";
      }
    }
  }

  .log-version-right {
    flex: 1;
    padding: 28px 30px 50px 45px;
    margin-left: 200px;
  }

  .markdowm-container {
    font-size: 14px;
    color: #313238;

    h1,
    h2,
    h3,
    h4,
    h5 {
      height: auto;
      margin: 10px 0;
      font:
        normal 14px/1.5
        "Helvetica Neue",
        Helvetica,
        Arial,
        "Lantinghei SC",
        "Hiragino Sans GB",
        "Microsoft Yahei",
        sans-serif;
      font-weight: bold;
      color: #34383e;
    }

    h1 {
      font-size: 30px;
    }

    h2 {
      font-size: 24px;
    }

    h3 {
      font-size: 18px;
    }

    h4 {
      font-size: 16px;
    }

    h5 {
      font-size: 14px;
    }

    em {
      font-style: italic;
    }

    div,
    p,
    font,
    span,
    li {
      line-height: 1.3;
    }

    p {
      margin: 0 0 1em;
    }

    table,
    table p {
      margin: 0;
    }

    ul,
    ol {
      padding: 0;
      margin: 0 0 1em 2em;
      text-indent: 0;
    }

    ul {
      padding: 0;
      margin: 10px 0 10px 15px;
      list-style-type: none;
    }

    ol {
      padding: 0;
      margin: 10px 0 10px 25px;
    }

    ol > li {
      line-height: 1.8;
      white-space: normal;
    }

    ul > li {
      padding-left: 15px !important;
      line-height: 1.8;
      white-space: normal;

      &::before {
        float: left;
        width: 6px;
        height: 6px;
        margin-top: calc(0.9em - 5px);
        margin-left: -15px;
        background: #000;
        border-radius: 50%;
        content: "";
      }
    }

    li > ul {
      margin-bottom: 10px;
    }

    li ol {
      padding-left: 20px !important;
    }

    ul ul,
    ul ol,
    ol ol,
    ol ul {
      margin-bottom: 0;
      margin-left: 20px;
    }

    ul.list-type-1 > li {
      padding-left: 0 !important;
      margin-left: 15px !important;
      list-style: circle !important;
      background: none !important;
    }

    ul.list-type-2 > li {
      padding-left: 0 !important;
      margin-left: 15px !important;
      list-style: square !important;
      background: none !important;
    }

    ol.list-type-1 > li {
      list-style: lower-greek !important;
    }

    ol.list-type-2 > li {
      list-style: upper-roman !important;
    }

    ol.list-type-3 > li {
      list-style: cjk-ideographic !important;
    }

    pre,
    code {
      width: 95%;
      padding: 0 3px 2px;
      font-family: Monaco, Menlo, Consolas, "Courier New", monospace;
      font-size: 14px;
      color: #333;
      border-radius: 3px;
    }

    code {
      padding: 2px 4px;
      font-family: Consolas, monospace, tahoma, Arial;
      color: #d14;
      border: 1px solid #e1e1e8;
    }

    pre {
      display: block;
      padding: 9.5px;
      margin: 0 0 10px;
      font-family: Consolas, monospace, tahoma, Arial;
      font-size: 13px;
      word-break: break-all;
      word-wrap: break-word;
      white-space: pre-wrap;
      background-color: #f6f6f6;
      border: 1px solid #ddd;
      border: 1px solid rgb(0 0 0 / 15%);
      border-radius: 2px;
    }

    pre code {
      padding: 0;
      white-space: pre-wrap;
      border: 0;
    }

    blockquote {
      padding: 0 0 0 14px;
      margin: 0 0 20px;
      border-left: 5px solid #dfdfdf;
    }

    blockquote p {
      margin-bottom: 0;
      font-size: 14px;
      font-weight: 300;
      line-height: 25px;
    }

    blockquote small {
      display: block;
      line-height: 20px;
      color: #999;
    }

    blockquote small::before {
      content: "\2014 \00A0";
    }

    blockquote::before,
    blockquote::after {
      content: "";
    }
  }
}

</style>
