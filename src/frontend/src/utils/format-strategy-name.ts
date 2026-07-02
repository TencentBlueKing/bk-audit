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
