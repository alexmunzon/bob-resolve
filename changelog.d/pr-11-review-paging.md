## PR 11: Review queue paging (2026-10-05)

- The review queue now renders up to 25 items at a time, with accessible page links and a stable filtered and total count.
- Suggestion and rule filters reset to page one, and the selected filters and page are preserved in the URL for bookmarks.
- Invalid page numbers and unknown filters in the URL fall back to page one and all items. The URL parser has its own tests.
- The page links wrap on narrow phone screens, and the queue says plainly when the chosen filters match nothing.
