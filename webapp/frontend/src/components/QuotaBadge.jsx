import { useEffect, useRef, useState } from "react";

function formatCountdown(totalSeconds) {
  const s = Math.max(0, Math.ceil(totalSeconds));
  const minutes = Math.floor(s / 60);
  const seconds = String(s % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

// Shows "Credits 28 / 40 · resets in 23:41". The countdown is anchored to the
// moment the quota arrived (reset_in_seconds), not to the server's clock, so a
// visitor's wrong system clock can't skew it. When it reaches zero the parent
// re-fetches the quota, which by then has rolled over to a fresh hour.
export default function QuotaBadge({ quota, onExpire }) {
  const [secondsLeft, setSecondsLeft] = useState(null);
  const expiredRef = useRef(false);

  useEffect(() => {
    if (!quota?.enabled) return undefined;
    const endsAt = Date.now() + quota.reset_in_seconds * 1000;
    expiredRef.current = false;
    const tick = () => {
      const left = (endsAt - Date.now()) / 1000;
      setSecondsLeft(left);
      if (left <= 0 && !expiredRef.current) {
        expiredRef.current = true;
        // Small delay so the request lands after the server's hour rolls over.
        setTimeout(onExpire, 1500);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [quota, onExpire]);

  if (!quota?.enabled || secondsLeft === null) return null;

  const sharedEmpty = quota.global_remaining <= 0;
  const low = quota.remaining <= Math.max(1, Math.floor(quota.limit * 0.2));
  return (
    <div className={`quota-badge ${quota.remaining === 0 || sharedEmpty ? "quota-empty" : low ? "quota-low" : ""}`}>
      <span className="quota-credits">
        Credits <strong>{quota.remaining}</strong> / {quota.limit}
      </span>
      <span className="quota-sep">·</span>
      <span className="quota-reset">resets in {formatCountdown(secondsLeft)}</span>
      {sharedEmpty && <span className="quota-shared">demo is busy - shared hourly limit reached</span>}
    </div>
  );
}
