// Total credits for running the selected models over `count` texts.
export function runCost(costPerText, count) {
  return costPerText * Math.max(count, 0);
}
