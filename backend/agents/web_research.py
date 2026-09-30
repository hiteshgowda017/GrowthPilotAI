import time
from ddgs import DDGS


def research_company(company_name: str) -> str:
    """Search the live web for multiple company-specific intents."""
    print(f"[WebResearch] Spawning semantic search crawlers for: {company_name}")

    search_queries = [
        f'"{company_name}" services solutions',
        f'"{company_name}" reviews profile',
        f'"{company_name}" digital presence market',
    ]
    collected_data = []

    try:
        with DDGS() as ddgs:
            for query in search_queries:
                try:
                    results = ddgs.text(query, max_results=3)
                    if not results:
                        continue
                    for result in results:
                        collected_data.append(
                            f"Title: {result.get('title', '')}\n"
                            f"Context: {result.get('body', '')}\n"
                            f"Source: {result.get('href', '')}\n"
                        )
                    time.sleep(0.5)
                except Exception as query_err:
                    print(f"[WebResearch] Query failed for '{query}': {query_err}")
    except Exception as connection_err:
        print(f"[WebResearch] DDGS connection failed: {connection_err}")

    if collected_data:
        return "\n".join(collected_data)

    return f"Live web research for {company_name} returned no verified results."
