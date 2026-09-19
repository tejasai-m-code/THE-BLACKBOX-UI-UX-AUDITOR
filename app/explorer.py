"""Bounded black-box multi-path explorer."""

from collections import deque

async def bounded_explore(page, base_url, max_paths=8, max_depth=3):
    queue = deque([(base_url, ["Home"], 0)])
    seen = set()
    paths = []
    while queue and len(paths) < max_paths:
        url, labels, depth = queue.popleft()
        if url in seen or depth > max_depth:
            continue
        seen.add(url)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=7000)
            suffix = page.url.replace(base_url, "", 1) or "/"
            nodes = labels + [suffix]
            paths.append({"nodes": nodes, "status": "explored", "depth": depth, "url": page.url})
            if depth >= max_depth:
                continue
            links = await page.locator("a[href]").evaluate_all(
                "els=>els.map(e=>({href:e.href,text:(e.innerText||e.getAttribute('aria-label')||'').trim()}))"
                ".filter(x=>x.href.includes('/target/')).slice(0,12)"
            )
            for link in links:
                if link["href"] not in seen:
                    queue.append((link["href"], labels + [link["text"] or "Link"], depth + 1))
        except Exception as exc:
            paths.append({"nodes": labels + ["ERROR"], "status": "error", "depth": depth, "error": str(exc)})
    return paths
