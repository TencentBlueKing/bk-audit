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
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showCreate"
    :show-footer="false"
    :title="isEditMode ? t('编辑联表') : t('新建联表')"
    :width="1050">
    <smart-action
      class="create-link-data"
      :offset-target="getSmartActionOffsetTarget">
      <bk-loading :loading="isEditDataLoading">
        <audit-form
          ref="formRef"
          form-type="vertical"
          :model="formData"
          :rules="rules">
          <bk-form-item
            class="is-required"
            :label="t('联表数据名称')"
            label-width="135"
            property="name">
            <bk-input
              v-model="formData.name"
              class="form-item-common"
              :maxlength="100"
              :over-max-length-limit="false"
              :placeholder="t('请输入联表数据名称')"
              show-word-limit />
          </bk-form-item>
          <bk-form-item
            :label="t('标签')"
            label-width="135"
            property="tags"
            style="flex: 1;">
            <bk-loading
              :loading="tagLoading"
              style="width: 100%;">
              <bk-select
                v-model="formData.tags"
                allow-create
                class="bk-select"
                filterable
                :input-search="false"
                multiple
                multiple-mode="tag"
                :placeholder="t('请选择')"
                :search-placeholder="t('请输入关键字')">
                <bk-option
                  v-for="(item) in tagData"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id" />
              </bk-select>
            </bk-loading>
          </bk-form-item>
          <bk-form-item
            class="is-required"
            :label="t('关联关系')"
            label-width="135"
            property="links">
            <links
              ref="linksRef"
              v-model:links="formData.config.links" />
          </bk-form-item>
        </audit-form>
      </bk-loading>
      <template #action>
        <bk-button
          class="w88"
          :loading="isSubmiting || isEditSubmiting"
          theme="primary"
          @click="handleSubmit">
          {{ isEditMode ? t('保存') : t('提交') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="closeDialog">
          {{ t('取消') }}
        </bk-button>
      </template>
    </smart-action>
  </audit-sideslider>
</template>
<script setup lang="ts">
  import { Message } from 'bkui-vue';
  import _ from 'lodash';
  import { h, provide, ref, watch  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import LinkDataManageService from '@service/link-data-manage';
  import MetaManageService from '@service/meta-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import Links from './components/links.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface IFormData {
    uid?: string,
    name: string,
    tags: Array<string>,
    config: {
      links: LinkDataDetailModel['config']['links']
    }
  }
  interface Emits {
    (e:'update'):void
    (e:'showLinkStrategy', value: string):void
  }
  interface Exposes {
    show(uid?:string):void
  }

  const emits = defineEmits<Emits>();

  const initFormData = {
    name: '',
    tags: [],
    config: {
      links: [{
        left_table: {
          rt_id: [],
          table_type: '',
          system_ids: [],
          display_name: '',
        },
        right_table: {
          rt_id: [],
          table_type: '',
          system_ids: [],
          display_name: '',
        },
        join_type: 'left_join',
        link_fields: [{
          left_field: {
            field_name: '',
            display_name: '',
          },
          right_field: {
            field_name: '',
            display_name: '',
          },
        }],
      }],
    },
  };

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const formRef = ref();
  const linksRef = ref();

  const showCreate = ref(false);
  const isEditMode = ref(false);
  const tagData = ref<Array<{
    id: string;
    name: string
  }>>([]);
  const strategyTagMap = ref<Record<string, string>>({});
  const formData = ref<IFormData>(_.cloneDeep(initFormData));
  const initLinks = ref<IFormData['config']['links']>([]);
  // 生成字母表数组
  const letters = Array.from({ length: 26 }, (_, i) => String.fromCharCode(97 + i));
  let letterIndex = -1;
  // 用于存储已分配的 display_name
  const displayNameMap: Record<string, string> = {};
  const isHasStrategy = ref<boolean | undefined>(false);
  const needUpdate = ref<boolean>(false);
  const editUid = ref<string | undefined>('');
  const styleElement = ref<null | HTMLStyleElement>(null);

  provide('isEditMode', isEditMode);

  const rules = {
    name: [
      {
        validator: (value: Array<any>) => !!value,
        message: t('联表数据名称不能为空'),
        trigger: 'blur',
      },
    ],
    tags: [
      // 因为校验的是name，但value是id的数组；将item转为name，自定义输入id = name，直接使用item即可
      {
        validator: (value: Array<string>) => {
          const reg = /^[\w\u4e00-\u9fa5-_]+$/;
          return value.every(item => reg.test(strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
        },
        message: t('标签只允许中文、字母、数字、中划线或下划线组成'),
        trigger: 'change',
      },
      {
        validator: (value: Array<string>) => {
          const reg = /\D+/;
          return value.every(item => reg.test(strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
        },
        message: t('标签不能为纯数字'),
        trigger: 'change',
      },
    ],
    'config.links': [
      {
        validator: (value: Array<any>) => value.length > 0,
        message: t('关联关系不能为空'),
        trigger: 'change',
      },
    ],
  };

  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');

  const closeDialog = () => {
    showCreate.value = false;
  };

  // 编辑
  const {
    run: fetchLinkDataDetail,
    loading: isEditDataLoading,
  } = useRequest(LinkDataManageService.fetchLinkDataDetail, {
    defaultValue: new LinkDataDetailModel(),
    onSuccess: (data) => {
      initLinks.value = _.cloneDeep(data.config.links);
      formData.value.uid = data.uid;
      formData.value.name = data.name;
      formData.value.tags = data.tags ? data.tags.map(item => item.toString()) : [];
      if (linksRef.value.setValue) {
        linksRef.value.setValue(data.config.links);
      }
    },
  });

  // 获取标签列表
  const {
    run: fetchTags,
    loading: tagLoading,
  } = useRequest(MetaManageService.fetchTags, {
    defaultValue: [],
    onSuccess(data) {
      tagData.value = data.reduce((res, item) => {
        if (item.tag_id !== '-2') {
          res.push({
            id: item.tag_id,
            name: item.tag_name,
          });
        }
        return res;
      }, [] as Array<{
        id: string;
        name: string
      }>);
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
      });
      if (isEditMode.value) {
        fetchLinkDataDetail({
          uid: editUid.value,
        });
      }
    },
  });

  // 保存联表
  const {
    run: addLinkTable,
    loading: isSubmiting,
  } = useRequest(LinkDataManageService.addLinkData, {
    defaultValue: {},
    onSuccess: () => {
      window.changeConfirm = false;
      messageSuccess(t('新建成功'));
      showCreate.value = false;
      emits('update');
    },
  });
  const {
    run: updateLinkTable,
    loading: isEditSubmiting,
  } = useRequest(LinkDataManageService.updateLinkData, {
    defaultValue: {},
    onSuccess: () => {
      window.changeConfirm = false;
      if (needUpdate.value) {
        Message({
          theme: 'success',
          message: h('div', [
            h('span', t('联表保存成功！请前往关联策略进行刷新升级。')),
            h('a', {
              onClick() {
                emits('showLinkStrategy', editUid.value as string);
              },
            }, t('查看关联策略')),
          ]),
        });
      } else {
        messageSuccess(t('编辑成功'));
      }
      showCreate.value = false;
      emits('update');
    },
  });

  const setDisplayName = (table: {
    name?: string;
    rt_id: string | Array<string>;
    table_type: string;
    system_ids?: Array<string>;
    display_name: string;
  }) => {
    const key = `${table.rt_id}`;
    if (!displayNameMap[key]) {
      // 分配一个新的字母
      displayNameMap[key] = letters[letterIndex += 1];
    }
    return displayNameMap[key];
  };

  // 提交
  const handleSubmit = () => {
    const tastQueue = [formRef.value.validate()];
    // 有配置组件
    if (linksRef.value.getValue) {
      tastQueue.push(linksRef.value.getValue());
    }
    Promise.all<IFormData>(tastQueue).then(([validator]) => {
      if (!isEditMode.value) {
        // eslint-disable-next-line no-param-reassign
        delete validator.uid;
      }
      const params = _.cloneDeep(validator);
      params.config.links = params.config.links.map((link) => {
        // 处理rt_id，如果是数组，取最后一个
        const leftTableRtId = link.left_table.rt_id;
        const rightTableRtId = link.right_table.rt_id;
        const item =  {
          ...link,
          left_table: {
            ...link.left_table,
            rt_id: (Array.isArray(leftTableRtId) ?  _.last(leftTableRtId)  : leftTableRtId) as string,
          },
          right_table: {
            ...link.right_table,
            rt_id: (Array.isArray(rightTableRtId) ?  _.last(rightTableRtId)  : rightTableRtId) as string,
          },
        };
        // 处理别名，如果相同的表，用一样的别名
        item.left_table.display_name =  setDisplayName(item.left_table);
        item.right_table.display_name =  setDisplayName(item.right_table);
        return item;
      });
      // 处理tag
      params.tags = params.tags.map(item => (strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
      const saveLinkData = isEditMode.value ? updateLinkTable : addLinkTable;
      const isNewVersion = !_.isEqual(initLinks.value, params.config.links);
      // 没有更改config，不传值
      if (!isNewVersion) {
        const noConfigParams: {
          uid?: string,
          name: string,
          tags: Array<string>,
          config?: {
            links: LinkDataDetailModel['config']['links']
          }
        } = {
          ...params,
        };
        delete noConfigParams.config;
        saveLinkData(noConfigParams);
      } else {
        // 如果有关联策略，并且联表更新了
        if (isHasStrategy.value) {
          needUpdate.value = true;
        }
        saveLinkData(params);
      }
    });
  };

  const addInlineStyle = (css: string) => {
    const style = document.createElement('style');
    style.type = 'text/css';
    style.appendChild(document.createTextNode(css));
    document.head.appendChild(style);
    return style; // 返回对 style 元素的引用
  };

  const removeInlineStyle = (styleElement: HTMLStyleElement) => {
    if (styleElement && styleElement.parentNode) {
      styleElement.parentNode.removeChild(styleElement);
    }
  };

  watch(() => showCreate.value, (data: boolean) => {
    if (data && !styleElement.value) {
      styleElement.value  = addInlineStyle('.bk-popover.bk-pop2-content.visible:not(.bk-select-popover):not(.link-data-join-type):not(.bk-cascader-popover) {display: none !important;}');
      return;
    }
    if (styleElement.value) {
      removeInlineStyle(styleElement.value);
      styleElement.value = null;
    }
  });

  defineExpose<Exposes>({
    show(uid?: string | undefined, hasStrategy?: boolean | undefined) {
      isHasStrategy.value = hasStrategy;
      editUid.value = uid;
      formData.value = _.cloneDeep(initFormData);
      showCreate.value = true;
      isEditMode.value = !!uid;
      fetchTags();
    },
  });
</script>
<style lang="postcss" scoped>
.create-link-data {
  padding: 24px;
  background-color: white;
}
</style>
