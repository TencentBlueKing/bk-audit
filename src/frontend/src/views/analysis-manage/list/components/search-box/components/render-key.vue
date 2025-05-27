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
  <div class="render-form-serach-key">
    <div
      class="box-row"
      :style="boxRowStyle">
      <template
        v-for="(fieldItem, fieldName) in defaultFieldList"
        :key="fieldName">
        <render-field-config
          ref="fieldConfigRef"
          :base-config="localFiledConfig"
          class="box-column"
          :model="localSearchModel"
          :name="fieldName"
          @change="handleChange" />
      </template>
      <div class="show-more-condition-btn">
        <bk-button
          text
          theme="primary"
          @click="handleShowMore">
          {{ t('更多选项') }}
          <audit-icon
            :class="{ active: isShowMore }"
            style=" margin-left: 4px;"
            type="angle-double-down" />
        </bk-button>
      </div>
    </div>
    <template v-if="isShowMore">
      <div
        class="box-row"
        :style="boxRowStyle">
        <template
          v-for="(fieldItem, fieldName) in moreFieldList"
          :key="fieldName">
          <render-field-config
            ref="fieldConfigRef"
            :base-config="localFiledConfig"
            class="box-column"
            :model="localSearchModel"
            :name="fieldName"
            @change="handleChange"
            @delete-field="handleDeleteField" />
        </template>
      </div>
      <!-- 新版查询不支持此参数 -->
      <div
        v-if="!isDoris.enabled"
        class="box-row">
        <render-field-config
          v-for="(fieldItem, fieldName) in queryStringField"
          :key="fieldName"
          ref="fieldConfigRef"
          :base-config="localFiledConfig"
          :model="localSearchModel"
          :name="fieldName"
          @change="handleChange" />
      </div>
    </template>
    <!-- 添加其他条件 -->
    <search-cascader
      :data="list"
      :filed-config="localFiledConfig"
      @select="handleCascaderSelect" />
    <!-- <div>
      <BkCheckbox>查询敏感数据</BkCheckbox>
    </div> -->
    <div
      class="mt16"
      style="display: flex;">
      <bk-button
        class="mr8"
        theme="primary"
        @click="handleSubmit">
        {{ t('查询') }}
      </bk-button>
      <bk-button
        class="mr8"
        @click="handleReset">
        {{ t('重置') }}
      </bk-button>
      <bk-button
        class="mr8"
        @click="() => isShowDataExport = !isShowDataExport">
        {{ t('导出') }}
      </bk-button>
      <bk-popover
        ref="favouriteQueryRef"
        :is-show="isShow"
        placement="bottom"
        theme="light"
        trigger="click"
        @after-hidden="handleAfterHidden">
        <bk-button
          class="mr8"
          @click="handleFavouriteQuery">
          {{ t('收藏此条件') }}
        </bk-button>
        <template #content>
          <div class="favourite-query-name">
            <span style="padding: 0 20px;">{{ t('收藏名称') }}</span>
            <bk-input
              v-model="favouriteSearch.name"
              :placeholder="t('请输入收藏名称')"
              style="width: 250px;" />
          </div>
          <div class="favourite-query-pop-bth">
            <bk-button
              class="mr8"
              size="small"
              theme="primary"
              @click="handleSubmitFavourite">
              {{ t('确定') }}
            </bk-button>
            <bk-button
              size="small"
              @click="handleCancel">
              {{ t('取消') }}
            </bk-button>
          </div>
        </template>
      </bk-popover>
      <bk-select
        filterable
        placeholder="请选择已收藏条件"
        style="width: 400px;"
        @select="handleSelectFavourite">
        <bk-option
          v-for="(item, index) in favouriteQueryList"
          :id="item.id"
          :key="index"
          class="favourite-item"
          :name="item.config_name">
          {{ item.config_name }}
          <audit-popconfirm
            :confirm-handler="()=>handleDeleteFavourite(item.id)"
            :content="t('删除后将不可找回')"
            :title="t('确认删除该收藏条件吗？')">
            <audit-icon
              class="favourite-item-close-icon"
              type="close" />
          </audit-popconfirm>
        </bk-option>
      </bk-select>
      <!-- <BkButton>添加跟踪策略</BkButton> -->
    </div>
    <!-- 数据导出 -->
    <data-export
      v-model:is-show="isShowDataExport"
      :data="list" />
  </div>
</template>
<script setup lang="ts">
  import dayjs from 'dayjs';
  import _ from 'lodash';
  import {
    computed,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import AccountManageService from '@service/account-manage';
  import EsQueryService from '@service/es-query';
  import MetaManageService from '@service/meta-manage';

  import AccountModel from '@model/account/account';

  import DataExport from './data-export/index.vue';
  import filedConfig from './render-field-config/config';
  import RenderFieldConfig from './render-field-config/index.vue';
  import SearchCascader from './search-cascader/index.vue';

  import useFeature from '@/hooks/use-feature';
  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface CascaderNode {
    allow_operators: string[]
    category?: string
    children: CascaderNode[]
    disabled: boolean
    dynamic_content: boolean
    id: string
    isJson: boolean
    level: number
    name: string
    isEdit: boolean
    isOpen: boolean;
  }

  interface Props {
    modelValue: Record<string, any>
  }

  interface Emits {
    (e: 'update:modelValue', value: Record<string, any>): void,
    (e: 'submit'): void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const { feature: isDoris } = useFeature('enable_doris');

  const isShow = ref(false);
  const favouriteQueryRef = ref();

  const isShowDataExport = ref(false);

  const localSearchModel = ref<Record<string, any>>({});
  const favouriteSearch = ref<Record<string, any>>({});
  const fieldConfigRef = ref();
  const isShowMore = ref(false);

  const localFiledConfig = ref(filedConfig);
  // eslint-disable-next-line max-len
  const allFieldNameList = computed(() => Object.keys(localFiledConfig.value) as Array<keyof typeof localFiledConfig.value>);
  const defaultFieldList = computed(() => allFieldNameList.value.slice(0, 7).reduce((result, fieldName) => ({
    ...result,
    [fieldName]: localFiledConfig.value[fieldName],
  }), {}));
  const moreFieldList = computed(() => allFieldNameList.value.slice(7).reduce((result, fieldName) => {
    if (fieldName === 'query_string') {
      return result;
    }
    return {
      ...result,
      [fieldName]: localFiledConfig.value[fieldName],
    };
  }, {}));

  const queryStringField = {
    query_string: localFiledConfig.value.query_string,
  };

  const list = ref<CascaderNode[]>([]);

  // eslint-disable-next-line max-len
  const convertToCascaderList = (arr: any[], level = 1, parentIds: string[] = []): CascaderNode[] => (Array.isArray(arr) ? arr.map((item: any) => {
    const currentId = item?.field_name ?? '';
    // 创建包含所有父级ID的数组
    const fullIds = level === 1 ?  [currentId] : [...parentIds, currentId];

    const children = item && item.property && Array.isArray(item.property.sub_keys)
      ? convertToCascaderList(item.property.sub_keys, level + 1, fullIds)
      : [];
    const newItem = {
      allow_operators: item?.allow_operators || [],
      children,
      category: item?.category ?? '',
      dynamic_content: item.property?.dynamic_content ?? false,
      disabled: false,
      id: level === 1 ? currentId : fullIds,
      isJson: item?.is_json ?? false,
      level,
      name: item?.description ?? item?.field_alias ?? '',
      isEdit: false,
      isOpen: false,
    };
    newItem.id = Array.isArray(newItem.id) ? JSON.stringify(newItem.id) : newItem.id;
    return newItem;
  }) : []);

  // 获取自定义检索字段
  const {
    data: SearchConfigList,
  } = useRequest(EsQueryService.fetchSearchConfig, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      console.log(SearchConfigList.value);
      list.value = convertToCascaderList(SearchConfigList.value);
    },
  });

  const {
    data: userInfo,
  } = useRequest(AccountManageService.fetchUserInfo, {
    defaultValue: new AccountModel(),
    manual: true,
    onSuccess: () => {
      fetchFavouriteQueryList({
        scene: 'search_config',
        created_by: userInfo.value.username,
      });
    },
  });

  // 获取收藏搜索条件列表
  const {
    run: fetchFavouriteQueryList,
    data: favouriteQueryList,
  } = useRequest(MetaManageService.fetchFavouriteQueryList, {
    defaultValue: [],
  });

  // 新增收藏搜索条件
  const {
    run: favouriteQueryCreate,
  } = useRequest(MetaManageService.favouriteQueryCreate, {
    defaultValue: {},
    onSuccess: () => {
      messageSuccess(t('收藏成功'));
      fetchFavouriteQueryList({
        scene: 'search_config',
        created_by: userInfo.value.username,
      });
      favouriteQueryRef.value.hide();
    },
  });

  // 更新收藏搜索条件
  const {
    run: favouriteQueryUpdate,
  } = useRequest(MetaManageService.favouriteQueryUpdate, {
    defaultValue: {},
    onSuccess: () => {
      messageSuccess(t('更新成功'));
      fetchFavouriteQueryList({
        scene: 'search_config',
        created_by: userInfo.value.username,
      });
      favouriteQueryRef.value.hide();
    },
  });

  // 删除收藏搜索条件
  const {
    run: favouriteQueryDelete,
  } = useRequest(MetaManageService.favouriteQueryDelete, {
    defaultValue: {},
    onSuccess: () => {
      messageSuccess(t('删除成功'));
      fetchFavouriteQueryList({
        scene: 'search_config',
        created_by: userInfo.value.username,
      });
    },
  });

  // 处理级联选择器选中事件，添加搜索项
  const handleCascaderSelect = (selectArr: CascaderNode[]) => {
    // 先检查并删除不在 selectArr 中的自定义字段
    const selectIds = selectArr.map(item => item.id).filter(Boolean);
    Object.keys(localFiledConfig.value).forEach((key) => {
      const config = localFiledConfig.value[key];
      if (config.customField && !selectIds.includes(key)) {
        // 如果是自定义字段且不在当前选中的数组中，则删除
        delete localFiledConfig.value[key];
      }
    });

    // 循环 selectArr 创建配置项
    selectArr.forEach((item) => {
      if (item && item.id) {
        // 判断 localFiledConfig.value 中是否已经存在该 id
        if (!localFiledConfig.value[item.id]) {
          // 如果不存在，则添加搜索项
          localFiledConfig.value[item.id] = {
            label: item.name,
            type: 'string',
            required: false,
            canClose: true,
            customField: true,
            operator: 'like', // 默认like
          };
        }
      }
    });
  };

  // 删除搜索项
  const handleDeleteField = (fieldName: keyof typeof localFiledConfig.value) => {
    // 删除对应的搜索项
    delete localFiledConfig.value[fieldName];
  };

  const handleAfterHidden = (value: { isShow: boolean}) => {
    isShow.value = value.isShow;
  };

  // 收藏搜索条件
  const handleFavouriteQuery = () => {
    favouriteSearch.value = _.cloneDeep(localSearchModel.value);
  };

  // 确认收藏搜索条件
  const handleSubmitFavourite = () => {
    // 查找是否存在同名的收藏条件
    const existingItem = favouriteQueryList.value.find(item => item.config_name === favouriteSearch.value.name);

    if (existingItem) {
      // 如果存在，使用该项的实际 id 进行更新
      favouriteQueryUpdate({
        id: existingItem.id, // 使用实际的 id
        scene: 'search_config',
        config_name: favouriteSearch.value.name,
        config_content: localSearchModel.value,
      });
    } else {
      // 如果不存在，创建新的收藏条件
      favouriteQueryCreate({
        scene: 'search_config',
        config_name: favouriteSearch.value.name,
        config_content: localSearchModel.value,
      });
    }
  };

  const handleCancel = () => {
    favouriteQueryRef.value.hide();
  };

  const handleSelectFavourite = (id: number) => {
    const item = favouriteQueryList.value.find((item: any) => item.id === id);
    if (item) {
      localSearchModel.value = item.config_content;

      // 先清空所有 isFavourite 为 true 的元素
      Object.keys(localFiledConfig.value).forEach((key) => {
        if (localFiledConfig.value[key]?.isFavourite === true) {
          console.log(111);
          delete localFiledConfig.value[key];
        }
      });

      // 对比 localSearchModel 和 localFiledConfig
      // 如果 localSearchModel 有的键在 localFiledConfig 中不存在，则添加
      Object.keys(localSearchModel.value).forEach((key) => {
        // 排除 datetime_origin 字段
        if (key !== 'datetime_origin' && !localFiledConfig.value[key]) {
          // 添加到 localFiledConfig
          localFiledConfig.value[key] = {
            label: (() => {
              // 尝试在 list.value 中查找匹配的节点
              const findNodeByKey = (nodes: CascaderNode[], searchKey: string): string | null => {
                for (const node of nodes) {
                  if (node.id === searchKey) {
                    return node.name;
                  }
                  if (node.children && node.children.length > 0) {
                    const found: string | null = findNodeByKey(node.children, searchKey);
                    if (found) return found;
                  }
                }
                return null;
              };

              // 在 list.value 中查找
              const foundName = findNodeByKey(list.value, key);
              return foundName || (() => {
                try {
                  const parsedKey = JSON.parse(key);
                  if (Array.isArray(parsedKey)) {
                    return parsedKey.slice(1).join('/');
                  }
                  return key;
                } catch (e) {
                  return key;
                }
              })();
            })(),
            type: 'string',
            required: false,
            canClose: true,
            isFavourite: true,
            operator: 'like', // 默认like
          };
        }
      });
    }
  };

  const handleDeleteFavourite = (id: number) => favouriteQueryDelete({
    id,
  });

  // 同步外部值的改动
  watch(() => props.modelValue, () => {
    localSearchModel.value = props.modelValue;
  }, {
    immediate: true,
  });

  // 显示更多搜索条件
  const handleShowMore = () => {
    isShowMore.value = !isShowMore.value;
  };
  // 搜索项值改变
  const handleChange = (fieldName: string, value: any) => {
    localSearchModel.value = {
      ...localSearchModel.value,
      [fieldName]: value,
    };
  };
  // 提交搜索
  const handleSubmit = () => {
    const getValues = fieldConfigRef.value.map((item: any) => item.getValue());
    Promise.all(getValues).then(() => {
      emits('update:modelValue', localSearchModel.value);
      emits('submit');
    });
  };
  // 重置所有搜索条件
  const handleReset = () => {
    localSearchModel.value = {
      datetime: [
        dayjs(Date.now() - 900000).format('YYYY-MM-DD HH:mm:ss'),
        dayjs().format('YYYY-MM-DD HH:mm:ss'),
      ],
      datetime_origin: [
        'now-15m',
        'now',
      ],
    };
  };

  const boxRowStyle = ref({
    'grid-template-columns': 'repeat(4, 1fr)',
  });

  const init = () => {
    const windowInnerWidth = window.innerWidth;
    boxRowStyle.value = windowInnerWidth < 1720 ? {
      'grid-template-columns': 'repeat(3, 1fr)',
    } : {
      'grid-template-columns': 'repeat(4, 1fr)',
    };
  };
  const resizeHandler = _.throttle(init, 100);

  onMounted(() => {
    init();
    window.addEventListener('resize', resizeHandler);
  });
  onBeforeUnmount(() => {
    window.removeEventListener('resize', resizeHandler);
  });
</script>
<style lang="postcss">
  .render-form-serach-key {
    position: relative;
    padding: 16px 24px;

    .box-row {
      display: grid;
      margin-bottom: 12px;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px 16px;

      .box-column {
        display: inline-block;
      }
    }

    .show-more-condition-btn {
      display: inline-block;
      margin-top: 35px;

      .active {
        transform: rotateZ(-180deg);
        transition: all .15s;
      }
    }
  }

  .favourite-query-name {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }

  .favourite-query-pop-bth {
    display: flex;
    height: 42px;
    align-items: center;
    justify-content: flex-end;
  }

  .favourite-item {
    justify-content: space-between;

    .favourite-item-close-icon {
      display: none;
    }

    &:hover {
      .favourite-item-close-icon {
        display: block;
      }
    }
  }
</style>
