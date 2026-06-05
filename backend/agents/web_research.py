import time
from duckduckgo_search import DDGS

def research_company(company_name: str) -> str:
    """
    Scrapes the live web across multiple intent targets for a specific company name.
    Executed inside a non-blocking thread pool managed by the calling agent.
    """
    print(f"[WebResearch] Spawning semantic search crawlers for: {company_name}")
    
    search_queries = [
        f'"{company_name}" services solutions',
        f'"{company_name}" reviews profile',
        f'"{company_name}" digital presence market'
    ]

    collected_data = []

    try:
        with DDGS() as ddgs:
            for query in search_queries:
                try:
                    # Execute individual targeted queries
                    results = ddgs.text(query, max_results=3)
                    if not results:
                        continue
                        
                    for result in results:
                        title = result.get("title", "")
                        body = result.get("body", "")
                        collected_data.append(f"Title: {title}\nContext: {body}\n")
                        
                    # Polite delay to prevent free tier rate limiting/IP bans
                    time.sleep(0.5)
                    
                except Exception as query_err:
                    print(f"[WebResearch] Query pass skipped for '{query}': {str(query_err)}")
                    continue
                    
    except Exception as connection_err:
        print(f"[WebResearch] Critical Scraper Engine failure: {str(connection_err)}")

    # Return structured corpus text or fallback string
    if collected_data:
        return "\n".join(collected_data)
    return f"Organic digital research footprint for {company_name} is currently secure or private."