import React from "react";

export function FeedList({ title, items, emptyText }) {
  return (
    <article className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
      </div>
      <div className="stack-list">
        {items.length ? (
          items.map((item, index) => (
            <div className="stack-item" key={index}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))
        ) : (
          <div className="empty">{emptyText}</div>
        )}
      </div>
    </article>
  );
}
