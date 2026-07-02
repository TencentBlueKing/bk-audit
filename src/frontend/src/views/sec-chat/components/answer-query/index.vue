<template>
  <div class="answer-query">
    <!-- 阶段1: 选择（根据类型显示不同选择器） -->
    <host-selector
      v-if="currentStep === 'select' && reportType === 'behavior'"
      v-model:dateTimeValue="dateTimeValue"
      v-model:timezone="timezone"
      @confirm="handleConfirm" />
    <risk-selector
      v-else-if="currentStep === 'select' && reportType === 'risk'"
      @confirm="handleRiskConfirm" />

    <!-- 回答四: 直接显示结果（不需要选择器和分析过程） -->
    <template v-else-if="reportType === 'hostDetail'">
      <div class="host-detail-header">
        <tool-steps :steps="hostDetailToolSteps" />

        <thinking-section :thinking-time="thinkingTime">
          <p>正在分析主机 {{ hostDetailInfo.ip }} 的行为记录...</p>
          <p>共发现 {{ hostDetailInfo.abnormalCount }} 条异常行为，{{ hostDetailInfo.relatedCount }} 条关联行为。</p>
        </thinking-section>

        <host-behavior-detail-report
          :attack-chain="hostDetailAttackChain"
          :findings="hostDetailFindings"
          :host-info="hostDetailInfo"
          :references="hostDetailReferences"
          :suggestions="hostDetailSuggestions"
          :timeline="hostDetailTimeline" />
        <result-footer
          @copy="handleCopy"
          @dislike="handleDislike"
          @export="handleExport"
          @like="handleLike"
          @refresh="handleRefresh" />
      </div>
    </template>

    <!-- 阶段2: 分析结果（回答二、三） -->
    <template v-else>
      <selected-info
        :host-count="totalRiskHosts"
        :hosts="selectedHosts"
        :report-type="reportType"
        :risks="selectedRisks"
        :time-range-text="timeRangeText"
        @edit="handleEditSelection" />

      <tool-steps :steps="currentSteps" />

      <thinking-section :thinking-time="thinkingTime">
        <p v-if="reportType === 'behavior'">
          正在检索主机行为记录...
        </p>
        <p v-else-if="reportType === 'risk'">
          正在检索所有未处理的高危及以上风险告警...
        </p>
        <p v-if="reportType === 'behavior'">
          共发现 128 条行为记录，涉及 2 台主机，运行状态正常。
        </p>
        <p v-else-if="reportType === 'risk'">
          共发现 {{ selectedRisks.length }} 条风险告警，涉及 {{ totalRiskHosts }} 台主机。
        </p>
      </thinking-section>

      <!-- 回答二: 主机行为分析报告(多主机) -->
      <analysis-report
        v-if="reportType === 'behavior'"
        :analysis-time="analysisTime"
        :hosts="selectedHosts"
        :suggestions="behaviorSuggestions"
        :time-range-text="timeRangeText"
        :total-behaviors="totalBehaviors"
        :total-risks="totalRisks" />

      <!-- 回答三: 主机风险告警解读报告 -->
      <risk-analysis-report
        v-else-if="reportType === 'risk'"
        :report-data="riskReportData" />

      <result-footer
        @copy="handleCopy"
        @dislike="handleDislike"
        @export="handleExport"
        @like="handleLike"
        @refresh="handleRefresh" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed, onMounted } from 'vue';
  import HostSelector from './host-selector.vue';
  import RiskSelector from './risk-selector.vue';
  import SelectedInfo from './selected-info.vue';
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  import ToolSteps from './tool-steps.vue';
  import type { ToolStep } from './tool-steps.vue';
  import ThinkingSection from './thinking-section.vue';
  import AnalysisReport from './analysis-report.vue';
  import RiskAnalysisReport from './risk-analysis-report.vue';
  import HostBehaviorDetailReport from './host-behavior-detail-report.vue';
  import ResultFooter from './result-footer.vue';

  const props = defineProps<{
    /** 用户发送的消息，用于自动判断报告类型 */
    prompt?: string;
  }>();

  // 阶段控制
  type Step = 'select' | 'analyzing' | 'result';
  const currentStep = ref<Step>('select');

  // 报告类型: behavior=主机行为分析(多主机), risk=风险告警解读, hostDetail=单主机行为分析详情
  // 根据 prompt 自动判断
  type ReportType = 'behavior' | 'risk' | 'hostDetail';
  const reportType = computed<ReportType>(() => {
    const msg = props.prompt?.toLowerCase() || '';
    if (msg.includes('风险告警') || msg.includes('解读风险') || msg.includes('风险解读')) {
      return 'risk';
    }
    // 匹配 "主机行为分析报告 — IP（主机名）" 格式，表示单主机详情
    if (msg.match(/主机行为分析报告\s*[-—]\s*\d+\.\d+\.\d+\.\d+/)) {
      return 'hostDetail';
    }
    return 'behavior';
  });

  // 时间选择器（仅回答二使用）
  const dateTimeValue = ref<[string, string]>(['', '']);
  const timezone = ref('UTC+8');

  const timeRangeText = computed(() => '近 1 小时');

  // 选择的主机（回答二）
  const selectedHosts = ref<any[]>([]);

  // 选择的风险（回答三）
  const selectedRisks = ref<any[]>([]);
  const totalRiskHosts = computed(() => new Set(selectedRisks.value.map(r => r.affectedAssets)).size);

  // 回答三的 mock 报告数据
  const riskReportData = computed(() => {
    const risks = selectedRisks.value;
    return {
      title: '主机风险告警解读报告',
      summary: {
        prefix: '本次解读共涉及',
        middle: '条风险告警，影响',
        suffix: '台主机',
      },
      riskOverview: {
        title: '风险概览',
      },
      riskDetail: {
        title: '逐条风险解读',
      },
      risks: risks.map(risk => ({
        id: risk.id,
        title: risk.name || risk.type,
        level: risk.level,
        levelText: risk.levelText,
        type: risk.type,
        findTime: risk.foundTime,
        affectedAssets: risk.affectedAssets,
        operator: risk.operator,
        description: `检测到主机 ${risk.affectedAssets} 存在${risk.type}风险，风险等级为${risk.levelText}，可能对系统安全造成严重影响。`,
        evidence: `攻击源 IP: 103.192.36.10，攻击方式: ${risk.type}，发生时间: ${risk.foundTime}，影响资产: ${risk.affectedAssets}。`,
        impact: `该风险可能导致主机 ${risk.affectedAssets} 被攻击者控制，进而影响同网络下的其他主机，造成数据泄露或服务中断。`,
        suggestions: [
          `立即处理该${risk.levelText}风险，遏制攻击进一步扩散`,
          `对主机 ${risk.affectedAssets} 进行全面安全检查`,
          '加强相关访问控制策略，防止类似事件再次发生',
        ],
      })),
      correlationAnalysis: {
        title: '关联分析',
        tip: '多条风险集中在同一主机时，通常表明存在系统性入侵，各风险之间可能构成完整的攻击链路（初始突破 → 信息收集 → 载荷执行 → 持久化 → 痕迹清理），建议按攻击链模型进行整体排查。',
      },
      suggestions: {
        title: '处置建议',
        list: [
          {
            priority: 'critical',
            priorityText: '紧急',
            risk: '暴力破解攻击',
            suggestion: '立即封禁攻击源 IP 103.192.36.10，阻止进一步攻击',
          },
          {
            priority: 'high',
            priorityText: '高',
            risk: '权限提升',
            suggestion: '修改受影响主机的 root 和应用密码',
          },
          {
            priority: 'medium',
            priorityText: '中',
            risk: '配置篡改',
            suggestion: '检查并修复被篡改的 SSH 配置文件',
          },
        ],
      },
      comprehensiveAdvice: {
        title: '综合建议',
        items: [
          '1. 立即处理严重和高级风险，优先遏制攻击链的进一步扩散',
          '2. 对受影响主机进行全面安全检查，确认是否存在其他未被检测到的威胁',
          '3. 建立常态化的安全巡检机制，及时发现和处理潜在风险',
        ],
      },
    };
  });

  // 回答四: 单主机行为分析详情的 mock 数据
  const hostDetailInfo = computed(() => ({
    ip: '10.0.1.5',
    name: 'web-prod-01',
    os: 'CentOS 7.9',
    riskScore: 92,
    riskLevel: '严重',
    timeRange: '近 24 小时',
    abnormalCount: 12,
    relatedCount: 5,
  }));

  const hostDetailFindings = computed(() => [
    {
      level: '严重',
      title: '境外IP异常登录',
      description: '2026-03-19 23:42，从境外IP <strong>45.33.32.156</strong> 通过SSH密码认证登录root账号，时间处于非工作时段',
    },
    {
      level: '严重',
      title: '恶意进程运行',
      description: '隐藏二进制文件 <strong>/tmp/x_cache</strong> 被创建并执行，该文件无数字签名，路径具有隐蔽特征',
    },
    {
      level: '严重',
      title: 'C2 反向连接',
      description: '恶意进程建立到 <strong>185.220.101.34:443</strong> 和 <strong>91.215.85.12:8080</strong> 的出站连接，疑似命令控制通信',
    },
    {
      level: '严重',
      title: '持久化后门',
      description: '通过 crontab 设置定时任务 <strong>*/10 * * * * /tmp/x_cache -d</strong>，确保恶意进程持久运行',
    },
    {
      level: '高危',
      title: '日志篡改',
      description: '<strong>/var/log/auth.log</strong> 在凌晨被修改，攻击者正在清除入侵痕迹',
    },
  ]);

  const hostDetailAttackChain = computed(() => ({
    rows: [
      {
        direction: 'right',
        nodes: [
          { title: '初始访问', subtitle: 'SSH暴力破解' },
          { title: '执行', subtitle: '信息收集命令' },
          { title: '持久化', subtitle: 'crontab后门' },
          { title: '凭证访问', subtitle: '/etc/shadow读取' },
        ],
      },
      {
        direction: 'left',
        nodes: [
          { title: '命令控制', subtitle: 'C2外联通信' },
          { title: '发现', subtitle: 'whoami/uname' },
          { title: '防御规避', subtitle: '日志篡改' },
        ],
      },
    ],
  }));

  const hostDetailTimeline = computed(() => [
    { time: '21:29:23', type: '登录行为', detail: 'SSH登录 root@45.33.32.156 (password)', level: '严重' },
    { time: '09:41:42', type: '进程启动', detail: 'bash -i (pid=28451)', level: '严重' },
    { time: '08:05:27', type: '登录行为', detail: 'whoami; id; uname -a', level: '严重' },
    { time: '06:31:12', type: '文件读取', detail: '/etc/shadow 被读取', level: '严重' },
    { time: '05:53:43', type: '文件写入', detail: '/tmp/x_cache (可疑二进制)', level: '严重' },
    { time: '05:45:10', type: '网络连接', detail: '→ 185.220.101.34:443 (C2)', level: '高危' },
    { time: '02:45:26', type: 'DNS查询', detail: 'crontab 新增持久化任务', level: '严重' },
    { time: '02:14:35', type: '计划任务', detail: 'update.cdn-edge.xyz (DGA域名)', level: '中危' },
    { time: '02:05:05', type: '进程启动', detail: 'auth.log 被篡改', level: '高危' },
    { time: '01:58:42', type: '文件修改', detail: 'crontab 新增持久化任务', level: '严重' },
  ]);

  const hostDetailSuggestions = computed(() => [
    {
      priority: 'critical',
      priorityText: '紧急',
      action: '隔离主机网络',
      description: '立即将 10.0.1.5 从生产网络断开，防止横向移动和数据外泄',
    },
    {
      priority: 'high',
      priorityText: '高',
      action: '重置所有密码',
      description: '重置 root 及所有服务账号密码，禁用密码认证方式',
    },
    {
      priority: 'medium',
      priorityText: '中',
      action: '取证备份',
      description: '对主机做完整磁盘镜像用于后续溯源分析',
    },
  ]);

  const hostDetailReferences = computed(() => [
    '安全运营-行为查询',
  ]);

  // 分析数据
  const thinkingTime = ref('0.8');
  const analysisTime = ref('');
  const totalBehaviors = ref(128);
  const totalRisks = ref(0);

  // 处置建议数据
  const behaviorSuggestions = ref([
    { priority: '建议', suggestion: '加强 SSH 访问控制，禁用密码登录', scope: '全部主机' },
    { priority: '建议', suggestion: '核查网络出站规则，封禁已知恶意 IP', scope: '全部主机' },
  ]);

  // 工具步骤（回答二）
  const toolSteps = ref<ToolStep[]>([
    {
      name: '查询主机行为',
      status: 'pending',
      detail: '',
      expanded: false,
    },
    {
      name: '生成分析报告',
      status: 'pending',
      detail: '',
      expanded: false,
    },
  ]);

  // 回答三的工具步骤
  const riskToolSteps = ref<ToolStep[]>([
    {
      name: '查询风险详情',
      status: 'pending',
      detail: JSON.stringify({ riskIds: [] }, null, 2),
      expanded: false,
    },
    {
      name: '关联威胁情报',
      status: 'pending',
      detail: JSON.stringify({ ioc: [] }, null, 2),
      expanded: false,
    },
    {
      name: '生成解读报告',
      status: 'pending',
      detail: '',
      expanded: false,
    },
  ]);

  // 回答四的工具步骤
  const hostDetailToolSteps = ref<ToolStep[]>([
    {
      name: '查询主机行为',
      status: 'done',
      detail: JSON.stringify({ hostIp: '10.0.1.5', timeRange: '近24小时' }, null, 2),
      expanded: false,
      elapsedTime: 320,
    },
    {
      name: '关联威胁情报',
      status: 'done',
      detail: JSON.stringify({ ioc: ['45.33.32.156', '185.220.101.34'] }, null, 2),
      expanded: false,
      elapsedTime: 280,
    },
    {
      name: '生成分析报告',
      status: 'done',
      detail: '',
      expanded: false,
      elapsedTime: 450,
    },
  ]);

  // 当前使用的工具步骤（根据 reportType 动态切换）
  const currentSteps = computed(() => {
    if (reportType.value === 'risk') return riskToolSteps.value;
    return toolSteps.value;
  });

  // 确认选择（回答二）
  const handleConfirm = (hosts: any[]) => {
    selectedHosts.value = hosts;
    currentStep.value = 'analyzing';
    startAnalysis('behavior');
  };

  // 确认选择（回答三）
  const handleRiskConfirm = (risks: any[]) => {
    selectedRisks.value = risks;
    // 更新工具步骤中的 riskIds
    riskToolSteps.value[0].detail = JSON.stringify({
      riskIds: risks.map(r => r.id),
    }, null, 2);
    riskToolSteps.value[1].detail = JSON.stringify({
      ioc: [...new Set(risks.map(r => r.affectedAssets))],
    }, null, 2);
    currentStep.value = 'analyzing';
    startAnalysis('risk');
  };

  // 返回修改
  const handleEditSelection = () => {
    currentStep.value = 'select';
  };

  // 开始分析
  const startAnalysis = (type: ReportType) => {
    analysisTime.value = new Date().toLocaleString('zh-CN');

    if (type === 'behavior') {
      // 回答二的动画
      setTimeout(() => {
        toolSteps.value[0].status = 'active';
      }, 100);

      setTimeout(() => {
        toolSteps.value[0].status = 'done';
        toolSteps.value[0].elapsedTime = 450;
        toolSteps.value[1].status = 'active';
      }, 600);

      setTimeout(() => {
        toolSteps.value[1].status = 'done';
        toolSteps.value[1].elapsedTime = 380;
        currentStep.value = 'result';
      }, 1000);
    } else {
      // 回答三的动画
      setTimeout(() => {
        riskToolSteps.value[0].status = 'active';
      }, 100);

      setTimeout(() => {
        riskToolSteps.value[0].status = 'done';
        riskToolSteps.value[0].elapsedTime = 450;
        riskToolSteps.value[1].status = 'active';
      }, 600);

      setTimeout(() => {
        riskToolSteps.value[1].status = 'done';
        riskToolSteps.value[1].elapsedTime = 380;
        riskToolSteps.value[2].status = 'active';
      }, 1000);

      setTimeout(() => {
        riskToolSteps.value[2].status = 'done';
        riskToolSteps.value[2].elapsedTime = 520;
        currentStep.value = 'result';
      }, 1500);
    }
  };

  // 底部操作
  const handleCopy = () => console.log('复制');
  const handleLike = () => console.log('点赞');
  const handleDislike = () => console.log('点踩');
  const handleRefresh = () => console.log('重新生成');
  const handleExport = () => console.log('导出报告');

  // 初始化
  onMounted(() => {
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 3600000);
    const pad = (n: number) => n.toString().padStart(2, '0');
    const format = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    dateTimeValue.value = [format(oneHourAgo), format(now)];
  });
</script>

<style lang="postcss" scoped>
.answer-query {
  padding: 20px 24px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgb(0 0 0 / 6%);

  /* 回答四头部样式：隐藏 ToolSteps 的分割线 */
  .host-detail-header {
    :deep(.tools-section .divider) {
      display: none;
    }
  }
}
</style>
