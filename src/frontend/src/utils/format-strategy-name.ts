export type StrategyOptionLike = {
  value?: string | number | null;
  label?: string | null;
  name?: string | null;
  strategy_name?: string | null;
  id?: string | number | null;
  strategy_id?: string | number | null;
};

export const findStrategyLabel = (
  strategyList: StrategyOptionLike[],
  strategyId?: string | number | null,
) => {
  if (strategyId === undefined || strategyId === null || strategyId === '') {
    return '';
  }
  const strategyIdText = String(strategyId);
  const matched = strategyList.find((item) => {
    const value = item.value ?? item.id ?? item.strategy_id;
    return value !== undefined && value !== null && String(value) === strategyIdText;
  });
  return String(matched?.label || matched?.name || matched?.strategy_name || '').trim();
};

export const formatStrategyNameWithId = (
  name?: string | null,
  id?: string | number | null,
) => {
  const strategyName = String(name || '').trim();
  if (id === undefined || id === null || id === '') {
    return strategyName || '--';
  }
  if (!strategyName) {
    return String(id);
  }
  return `${strategyName} (${id})`;
};

export const formatStrategyOptionLabel = (item: Record<string, any>) => {
  const id = item.value ?? item.id ?? item.strategy_id;
  const name = item.label || item.name || item.strategy_name || '';
  return formatStrategyNameWithId(name, id);
};
