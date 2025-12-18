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
class Log {
  batch: Array<string>;
  bizid: number;
  cloudid: number;
  data: string;
  dataid: number;
  datetime: string;
  ext: Record<any, any>;
  filename: string;
  gseindex: number;
  hostname: string;
  ip: string;
  items: Array<{ data: string; iterationindex: number }>;
  iterationindex: number;
  log: string;
  time: number;
  utctime: string;
  constructor(payload = {} as Log) {
    this.batch = payload.batch;
    this.bizid = payload.bizid;
    this.cloudid = payload.cloudid;
    this.data = payload.data;
    this.dataid = payload.dataid;
    this.datetime = payload.datetime;
    this.ext = payload.ext;
    this.filename = payload.filename;
    this.gseindex = payload.gseindex;
    this.hostname = payload.hostname;
    this.ip = payload.ip;
    this.items = payload.items;
    this.iterationindex = payload.iterationindex;
    this.log = payload.log;
    this.time = payload.time;
    this.utctime = payload.utctime;
  }
}

export default class TailLog {
  etl: Log;
  origin: Log;
  constructor(payload = {} as TailLog) {
    this.etl = this.initEtl(payload.etl);
    this.origin = this.initOrigin(payload.origin);
  }

  get originData() {
    if (this.origin.items.length < 1) {
      return '';
    }
    return this.origin.items[0].data;
  }

  initEtl(etl: Log) {
    return new Log(etl);
  }

  initOrigin(origin: Log) {
    return new Log(origin);
  }
}
