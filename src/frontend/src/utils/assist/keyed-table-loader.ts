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
export interface TableLoadState<T> {
  loading: boolean;
  loaded: boolean;
  data?: T;
  error?: Error;
}

/** 实例内按完整请求键去重；关闭后的旧请求不得写回状态或继续修改节点。 */
export const createKeyedTableLoader = <T, C extends { cancel: () => void }>(
  states: Record<string, TableLoadState<T>>,
  createCancel: () => C,
) => {
  const pending = new Map<string, Promise<T>>();
  const sources = new Set<C>();
  let generation = 0;
  const load = (key: string, request: (source: C) => Promise<T>): Promise<T> => {
    if (states[key]?.loaded) return Promise.resolve(states[key].data as T);
    if (pending.has(key)) return pending.get(key)!;
    const source = createCancel();
    const current = generation;
    sources.add(source);
    states[key] = { loading: true, loaded: false };
    const task = Promise.resolve().then(() => {
      if (current !== generation) throw new Error('Request cancelled');
      return request(source);
    }).then((data) => {
      if (current !== generation) throw new Error('Request cancelled');
      states[key] = { loading: false, loaded: true, data };
      return data;
    }).catch((error) => {
      if (current === generation) states[key] = { loading: false, loaded: false, error };
      throw error;
    }).finally(() => {
      sources.delete(source);
      if (current === generation) pending.delete(key);
    });
    pending.set(key, task);
    return task;
  };
  const cancel = () => {
    generation += 1;
    sources.forEach(source => source.cancel());
    sources.clear();
    pending.clear();
    Object.keys(states).forEach((key) => {
      if (states[key].loading) states[key] = { loading: false, loaded: false };
    });
  };
  return { load, cancel };
};
