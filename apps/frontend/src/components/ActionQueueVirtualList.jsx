import React, { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_ROW_HEIGHT = 76;

/**
 * Lightweight windowed list (no extra deps). Renders only visible rows + overscan.
 */
export function ActionQueueVirtualList({
  items,
  rowHeight = DEFAULT_ROW_HEIGHT,
  maxHeight = 480,
  renderRow,
  onEndReached,
  hasMore,
}) {
  const containerRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportH, setViewportH] = useState(maxHeight);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setViewportH(el.clientHeight || maxHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, [maxHeight]);

  const totalH = items.length * rowHeight;
  const overscan = 3;
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visibleCount = Math.ceil(viewportH / rowHeight) + overscan * 2;
  const end = Math.min(items.length, start + visibleCount);
  const slice = items.slice(start, end);
  const offsetY = start * rowHeight;

  const onScroll = useCallback(
    (e) => {
      const top = e.target.scrollTop;
      setScrollTop(top);
      if (hasMore && onEndReached) {
        const nearBottom = top + e.target.clientHeight >= totalH - rowHeight * 2;
        if (nearBottom) onEndReached();
      }
    },
    [hasMore, onEndReached, totalH, rowHeight],
  );

  return (
    <div
      ref={containerRef}
      className="overflow-y-auto"
      style={{ maxHeight }}
      onScroll={onScroll}
      data-testid="aq-virtual-list"
    >
      <div style={{ height: totalH, position: "relative" }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {slice.map((item, i) => (
            <div key={item.id} style={{ minHeight: rowHeight }}>
              {renderRow(item, start + i)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
