/*
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
*/
import _ from 'lodash';
import {
  type ComponentInternalInstance,
  computed,
  getCurrentInstance,
} from 'vue';

interface Props {
  name: string,
  model: Record<string, any>
}

export default function (props: Props, allText: string) {
  const currentInstance = getCurrentInstance() as ComponentInternalInstance;

  const modelValue = computed<Array<string | number>>(() => {
    const lastValue = props.model[props.name];
    return lastValue && lastValue.length > 0
      ? lastValue.map((item: string) => (isNaN(Number(item)) ? item : Number(item))) : [allText];
  });

  const selectedAll = computed(() => modelValue.value.includes(allText));

  const handleChange = (value: Array<string | number>) => {
    const result = [...value];
    _.remove(result, item => item === allText);
    currentInstance.emit('change', props.name, result);
  };

  const handleSubmit = () => {
    currentInstance.emit('submit');
  };

  const handleCancel = () => {
    currentInstance.emit('cancel');
  };

  return {
    modelValue,
    selectedAll,
    handleChange,
    handleSubmit,
    handleCancel,
  };
}
