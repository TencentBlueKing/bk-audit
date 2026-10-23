import type { ExecutionStatus, ExecutionTrigger } from './execution-record';

export interface ExecutionListQuery {
  page?: number;
  page_size?: number;
  task_id?: string;
  task_name?: string;
  application_id?: string;
  application_name?: string;
  risk_id?: string;
  trigger_type?: string;
  status?: string;
  executor?: string;
  sort?: string | string[];
  scene_id?: string;
}

const toNumber = (value?: string) => {
  if (value == null || value === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const mapOrderBy = (sort?: string | string[]) => {
  const raw = Array.isArray(sort) ? sort[0] : sort;
  if (!raw) return undefined;
  const desc = String(raw).startsWith('-');
  const field = String(raw).replace(/^-/, '');
  const mapped = field === 'started_at' ? 'start_time'
    : field === 'executor' ? 'operator'
      : field === 'duration' ? 'duration'
        : '';
  if (!mapped) return undefined;
  return desc ? `-${mapped}` : mapped;
};

/** 页面筛选名转成执行记录列表协议的 query。任务 ID 筛选项对应协议 id（记录主键）。 */
export const toExecutionListQuery = (params: ExecutionListQuery = {}) => {
  const query: Record<string, string | number> = {};
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  const paId = toNumber(params.application_id);
  if (paId != null) query.pa_id = paId;
  if (params.application_name) query.pa_name = params.application_name;
  if (params.risk_id) query.risk_id = params.risk_id;
  const sceneId = toNumber(params.scene_id);
  if (sceneId != null) query.scene_id = sceneId;
  if (params.task_id) query.id = params.task_id;
  if (params.task_name) query.task_name = params.task_name;
  if (params.trigger_type) query.trigger = params.trigger_type === 'retry' ? 'test' : params.trigger_type;
  if (params.status) query.result = params.status;
  if (params.executor) query.operator = params.executor;
  const orderBy = mapOrderBy(params.sort);
  if (orderBy) query.order_by = orderBy;
  return query;
};

/** 不足 1 分只显示秒。已有更大单位且秒数为 0 时不再带「00秒」，例如 1分、1小时2分。单独的 0 仍显示为 0秒。 */
export const formatDurationClock = (totalSeconds: number) => {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  if (seconds < 60) return `${seconds}秒`;
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    return rest ? `${minutes}分${String(rest).padStart(2, '0')}秒` : `${minutes}分`;
  }
  if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes ? `${hours}小时${minutes}分` : `${hours}小时`;
  }
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  return hours ? `${days}天${hours}小时` : `${days}天`;
};

export const formatExecutionDuration = (value: unknown) => {
  if (value == null || value === '') return '';
  if (typeof value === 'number' && Number.isFinite(value)) return formatDurationClock(value);
  const text = String(value).trim();
  const seconds = text.match(/^(\d+)\s*秒$/);
  if (seconds) return formatDurationClock(Number(seconds[1]));
  return text;
};

const parseStartedAt = (value: string) => {
  const parsed = Date.parse(value);
  if (!Number.isNaN(parsed)) return parsed;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/);
  if (!match) return Number.NaN;
  return new Date(`${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}`).getTime();
};

/** 执行中按开始时间到 now 计算耗时；已结束沿用接口返回值。 */
export const resolveExecutionDuration = (
  status: string,
  startedAt: string,
  fallback: string,
  now = Date.now(),
) => {
  if (status !== 'running') return fallback || '--';
  const start = parseStartedAt(startedAt || '');
  if (Number.isNaN(start)) return fallback || '--';
  const seconds = Math.max(0, Math.floor((now - start) / 1000));
  return formatDurationClock(seconds);
};

const joinList = (value: unknown) => {
  if (Array.isArray(value)) return value.filter(Boolean).join(', ');
  if (value == null) return '';
  return String(value);
};

export const normalizeExecutionResult = (value: unknown): ExecutionStatus => {
  const text = String(value || '').toLowerCase();
  if (text === 'success' || text === 'finished') return 'success';
  if (text === 'failed' || text === 'revoked' || text === 'expired') return 'failed';
  return 'running';
};

export const normalizeNodeState = (value: unknown): ExecutionStatus => {
  const upper = String(value || '').toUpperCase();
  if (upper === 'FINISHED') return 'success';
  if (upper === 'FAILED' || upper === 'REVOKED' || upper === 'EXPIRED') return 'failed';
  if (upper === 'CREATED' || upper === 'RUNNING') return 'running';
  return normalizeExecutionResult(value);
};

const asTrigger = (value: unknown): ExecutionTrigger => {
  const text = String(value || '');
  if (text === 'manual' || text === 'auto' || text === 'test' || text === 'retry') return text;
  return '';
};

export const mapExecutionRecord = (item: Record<string, any> = {}) => ({
  task_id: String(item.id || ''),
  task_name: item.task_name || '',
  application_id: item.pa_id == null ? '' : String(item.pa_id),
  application_name: item.pa_name || '',
  risk_id: item.risk_id || '',
  trigger_type: asTrigger(item.trigger),
  started_at: item.start_time || '',
  duration: formatExecutionDuration(item.duration),
  ended_at: item.finish_time || '',
  status: normalizeExecutionResult(item.result),
  error: item.failure_hint || '',
  executor: item.operator || '',
  scene_id: '',
  is_test: !!item.is_test,
  sops_task_id: item.sops_task_id == null ? '' : String(item.sops_task_id),
  sops_task_url: item.sops_task_url || '',
});

const mapNodes = (rawAttempts: Record<string, any>[]) => rawAttempts.map(attempt => ({
  name: attempt.node_name || attempt.node_id || '',
  status: normalizeNodeState(attempt.state),
  started_at: attempt.start_time || '',
  duration: formatExecutionDuration(attempt.duration),
  error: attempt.error_message || '',
}));

const earliest = (values: string[]) => values.filter(Boolean).sort()[0] || '';
const latest = (values: string[]) => values.filter(Boolean).sort().slice(-1)[0] || '';

/** 一次重试里的节点耗时：优先用节点起止时间，否则累加接口秒数。0 保留，没有数值才留空。 */
const retryDuration = (rawAttempts: Record<string, any>[], startedAt: string, endedAt: string) => {
  const start = parseStartedAt(startedAt);
  const end = parseStartedAt(endedAt);
  if (!Number.isNaN(start) && !Number.isNaN(end) && end >= start) {
    return formatDurationClock((end - start) / 1000);
  }
  const seconds = rawAttempts
    .map(attempt => attempt?.duration)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!seconds.length) return '';
  return formatDurationClock(seconds.reduce((sum, value) => sum + value, 0));
};

const mapRetryRounds = (history: Record<string, any>[]) => [...history]
  .sort((left, right) => String(left.time || '').localeCompare(String(right.time || '')))
  .map((entry, index) => {
    const rawAttempts = Array.isArray(entry.attempts) ? entry.attempts : [];
    const nodes = mapNodes(rawAttempts);
    const startedAt = entry.time || earliest(nodes.map(node => node.started_at)) || '';
    const endedAt = latest(rawAttempts.map(attempt => String(attempt.end_time || '')));
    const failed = nodes.find(node => node.status === 'failed' && node.error);
    const status: ExecutionStatus = nodes.some(node => node.status === 'failed')
      ? 'failed'
      : nodes.some(node => node.status === 'running')
        ? 'running'
        : 'success';
    return {
      id: `retry-${index + 1}`,
      label: '',
      status,
      started_at: startedAt,
      ended_at: endedAt,
      duration: retryDuration(rawAttempts, startedAt, endedAt),
      executor: entry.operator || '',
      error: failed?.error || '',
      nodes,
    };
  });

/** 当前 attempts 是最后一轮节点，接在 retry_history 之后。 */
const mapCurrentRound = (item: Record<string, any>, rawAttempts: Record<string, any>[], index: number) => {
  const nodes = mapNodes(rawAttempts);
  const startedAt = item.start_time || earliest(nodes.map(node => node.started_at)) || '';
  const endedAt = item.finish_time || latest(rawAttempts.map(attempt => String(attempt.end_time || '')));
  const failed = nodes.find(node => node.status === 'failed' && node.error);
  const recordedDuration = formatExecutionDuration(item.duration);
  return {
    id: `retry-${index + 1}`,
    label: '',
    status: item.result ? normalizeExecutionResult(item.result) : (
      nodes.some(node => node.status === 'failed')
        ? 'failed'
        : nodes.some(node => node.status === 'running')
          ? 'running'
          : 'success'
    ),
    started_at: startedAt,
    ended_at: endedAt,
    duration: recordedDuration || retryDuration(rawAttempts, startedAt, endedAt),
    executor: item.operator || '',
    error: item.failure_hint || failed?.error || '',
    nodes,
  };
};

export const mapExecutionDetail = (item: Record<string, any> = {}) => {
  const params = item.params || {};
  const rawAttempts = Array.isArray(item.attempts) ? item.attempts : [];
  const nodes = mapNodes(rawAttempts);
  const retryHistory = Array.isArray(item.retry_history) ? item.retry_history : [];
  const historyRounds = mapRetryRounds(retryHistory);
  const rounds = historyRounds.length
    ? [...historyRounds, mapCurrentRound(item, rawAttempts, historyRounds.length)]
    : [];
  return {
    task_id: String(item.id || ''),
    sops_task_id: item.sops_task_id == null ? '' : String(item.sops_task_id),
    sops_task_url: item.sops_task_url || '',
    task_name: item.task_name || '',
    application_id: item.pa_id == null ? '' : String(item.pa_id),
    application_name: item.pa_name || '',
    risk_id: item.risk_id || '',
    risk_title: item.risk_title || '',
    risk_level: item.risk_level || '',
    risk_owner: joinList(params.operator),
    risk_type: joinList(params.risk_type),
    risk_evidence: joinList(params.risk_evidence),
    risk_source: params.risk_source || '',
    risk_description: params.risk_description || '',
    risk_found_at: params.risk_time || '',
    strategy_id: params.strategy_id == null ? '' : String(params.strategy_id),
    strategy_name: params.strategy_name || '',
    raw_event_id: params.raw_event_id || '',
    trigger_type: asTrigger(item.trigger),
    started_at: item.start_time || '',
    ended_at: item.finish_time || '',
    duration: formatExecutionDuration(item.duration),
    status: normalizeExecutionResult(item.result),
    error: item.failure_hint || '',
    executor: item.operator || '',
    scene_id: '',
    is_test: !!item.is_test,
    params: [],
    nodes,
    attempts: rounds,
  };
};

export const mapExecutionList = (data: Record<string, any> = {}) => ({
  results: (Array.isArray(data.results) ? data.results : []).map(mapExecutionRecord),
  page: data.page,
  num_pages: data.num_pages,
  total: data.count ?? data.total ?? 0,
});
