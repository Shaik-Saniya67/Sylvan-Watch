/** 2x2 confusion matrix: rows = Hansen reference, columns = prediction. */
export function ConfusionMatrix({ matrix }: { matrix: number[][] }) {
  const cells = [
    { v: matrix[0][0], label: "stable → stable", tone: "bg-mint" }, { v: matrix[0][1], label: "stable → loss (false alarm)", tone: "bg-peach" },
    { v: matrix[1][0], label: "loss → stable (missed)", tone: "bg-peach" }, { v: matrix[1][1], label: "loss → loss", tone: "bg-mint" },
  ];
  return (
    <div className="grid grid-cols-2 gap-1.5 text-center text-xs">
      {cells.map((c) => (
        <div key={c.label} className={`rounded-xl p-3 ${c.tone}`}>
          <div className="font-display text-xl">{c.v.toLocaleString()}</div><div className="text-muted">{c.label}</div>
        </div>
      ))}
    </div>
  );
}
