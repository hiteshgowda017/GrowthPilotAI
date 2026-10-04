import re
from urllib.parse import urlparse

NOISE_TERMS = {
    "film", "movie", "trailer", "novel", "book", "story", "fiction",
    "actor", "actress", "cast", "episode", "season", "soundtrack",
    "imdb", "youtube", "wikipedia", "wiki", "lyrics", "song", "album",
    "comic", "character", "tv show", "television", "series", "cinema",
    "review of the film", "movie review",
}

DIRECTORY_DOMAINS = {
    "justdial.com", "sulekha.com", "indiamart.com", "google.com",
    "facebook.com", "instagram.com", "linkedin.com",
}

GENERIC_TITLE_PREFIXES = (
    "top ", "best ", "list of", "directory", "companies in ",
    "businesses in ", "near me", "leading ", "largest ",
)

LOCATION_ALIASES = {
    "bengaluru": {"bengaluru", "bangalore"},
    "bangalore": {"bengaluru", "bangalore"},
    "mumbai": {"mumbai", "bombay"},
    "kolkata": {"kolkata", "calcutta"},
    "chennai": {"chennai", "madras"},
    "pune": {"pune"},
}

def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()

def _tokens(value: str) -> list[str]:
    return [x for x in re.findall(r"[a-z0-9]+", _norm(value)) if len(x) > 2]

def expand_industry_terms(industry: str) -> set[str]:
    raw = _norm(industry)
    terms = set(_tokens(raw))
    if raw in {"it", "it services", "information technology", "software"} or "software" in raw or "technology" in raw:
        terms.update({
            "information technology", "it services", "software",
            "software development", "technology", "technology consulting",
            "cloud", "cybersecurity", "digital solutions", "managed services",
        })
    if "digital marketing" in raw or "marketing" in raw:
        terms.update({"digital marketing", "seo", "social media", "branding", "performance marketing"})
    if "education" in raw or "school" in raw or "training" in raw:
        terms.update({"education", "school", "training", "academy", "learning"})
    if "health" in raw or "diagnostic" in raw or "hospital" in raw:
        terms.update({"healthcare", "diagnostic", "hospital", "medical", "clinic", "pathology"})
    return terms

def expand_location_terms(location: str) -> set[str]:
    raw = _norm(location)
    terms = set(_tokens(raw))
    for key, aliases in LOCATION_ALIASES.items():
        if key in raw or any(alias in raw for alias in aliases):
            terms.update(aliases)
    return terms

def parse_search_results(raw: str) -> list[dict]:
    pattern = re.compile(
        r"(?:SEARCH QUERY:\s*(?P<query>[^\n]*)\n)?"
        r"-\s*(?P<title>.*?)\n\s*(?P<body>.*?)\n\s*Source:\s*(?P<href>\S+)",
        re.DOTALL,
    )
    items = []
    for match in pattern.finditer(raw or ''):
        title = " ".join(match.group("title").split())
        body = " ".join(match.group("body").split())
        href = match.group("href").strip()
        query = " ".join((match.group("query") or "").split())
        if title or body or href:
            items.append({
                "title": title,
                "body": body,
                "href": href,
                "query": query,
            })
    return items

def _is_noise(item: dict) -> bool:
    text = _norm(" ".join([item.get("title", ""), item.get("body", ""), item.get("href", "")]))
    return any(term in text for term in NOISE_TERMS)

def candidate_name(title: str, href: str) -> str:
    value = " ".join((title or "").split())
    value = re.sub(r"\s*[|]\s*(Justdial|Sulekha|IndiaMART|Facebook|Instagram|LinkedIn|YouTube|IMDb|Wikipedia).*?$", "", value, flags=re.I)
    value = re.sub(r"\s*[-–—]\s*(Justdial|Sulekha|IndiaMART|Facebook|Instagram|LinkedIn|YouTube|IMDb|Wikipedia).*?$", "", value, flags=re.I)
    value = value.strip(' -|:')
    low = value.lower()

    # Never turn a generic article/category title into a competitor.
    if not value or any(low.startswith(prefix) for prefix in GENERIC_TITLE_PREFIXES):
        try:
            host = urlparse(href).netloc.lower().replace("www.", "")
            if not host or any(d in host for d in DIRECTORY_DOMAINS):
                return ''
            return host.split('.')[0].replace('-', ' ').strip()
        except Exception:
            return ''

    # Reject obvious generic/non-company titles even when the URL itself is
    # not a blocked domain.
    generic = {
        "software", "application software", "information technology",
        "information technology services", "it services", "technology",
        "computer software", "software company", "companies", "businesses",
        "home", "services", "solutions", "about us", "contact us",
    }
    if low in generic:
        return ''

    return value[:120]

def _match_score(item: dict, industry: str, location: str, role: str, target_name: str = '') -> int:
    if _is_noise(item):
        return -1000
    title = _norm(item.get("title", ""))
    body = _norm(item.get("body", ""))
    href = _norm(item.get("href", ""))
    corpus = " ".join([title, body, href])
    industry_terms = expand_industry_terms(industry)
    location_terms = expand_location_terms(location)
    score = 0
    industry_hits = sum(1 for term in industry_terms if term in title)
    industry_body_hits = sum(1 for term in industry_terms if term in body)
    location_hits = sum(1 for term in location_terms if term in title)
    location_body_hits = sum(1 for term in location_terms if term in body)

    # Generic words such as "services" are not enough to establish an IT
    # company. Require at least one strong sector signal for software/IT.
    raw_industry = _norm(industry)
    if raw_industry in {"it", "it services", "information technology", "software"} or "software" in raw_industry or "technology" in raw_industry:
        strong_terms = {
            "information technology", "it services", "software",
            "software development", "technology", "technology consulting",
            "cloud", "cybersecurity", "managed services", "saas",
            "app development", "web development", "digital transformation",
            "erp", "crm", "data analytics", "artificial intelligence",
        }
        strong_title = sum(1 for term in strong_terms if term in title)
        strong_body = sum(1 for term in strong_terms if term in body)
        if strong_title + strong_body == 0:
            return -1000

    score += min(industry_hits * 25, 50)
    score += min(industry_body_hits * 8, 24)

    # Prefer pages that look like an actual company presence rather than
    # generic knowledge pages. This is still evidence scoring, not a claim
    # about company quality.
    host = urlparse(item.get("href", "")).netloc.lower().replace("www.", "")
    title_has_company_signal = any(
        token in title for token in ("pvt", "private", "ltd", "limited", "technologies",
                                     "technology", "solutions", "systems", "labs",
                                     "software", "digital", "consulting", "services",
                                     "inc", "llc", "corp", "group")
    )
    if host and not any(d in host for d in DIRECTORY_DOMAINS):
        score += 12
    if title_has_company_signal:
        score += 8
    if role == 'local':
        score += min(location_hits * 25, 50)
        score += min(location_body_hits * 8, 24)
        if any(domain in href for domain in DIRECTORY_DOMAINS):
            score += 6
        if not (location_hits or location_body_hits):
            return -1000
        if not (industry_hits or industry_body_hits):
            return -1000
    elif role == 'global':
        if any(x in corpus for x in ['worldwide', 'global', 'international', 'multinational', 'countries', 'continents']):
            score += 12
        if not (industry_hits or industry_body_hits):
            return -1000
    else:
        target = _norm(target_name)
        if target and target in corpus:
            score += 70
        else:
            return -1000
    return score

def rank_candidates(raw: str, industry: str, location: str, role: str, target_name: str = '', limit: int = 5) -> list[dict]:
    items = parse_search_results(raw)
    ranked = []
    for item in items:
        score = _match_score(item, industry, location, role, target_name)
        if score < 35:
            continue
        name = candidate_name(item.get('title', ''), item.get('href', ''))
        if not name:
            continue
        if target_name and _norm(name) == _norm(target_name):
            continue
        ranked.append((score, name, item))

    dedup: dict[str, dict] = {}
    for score, name, item in ranked:
        host = urlparse(item.get('href', '')).netloc.lower().replace('www.', '')
        key = host if host and not any(d in host for d in DIRECTORY_DOMAINS) else _norm(name)
        current = dedup.get(key)
        if not current or score > current['score']:
            dedup[key] = {'score': score, 'name': name, 'sources': [item.get('href', '')], 'snippets': [item.get('body', '')]}
        else:
            if item.get('href') and item['href'] not in current['sources']:
                current['sources'].append(item['href'])
            if item.get('body') and item['body'] not in current['snippets']:
                current['snippets'].append(item['body'])

    ordered = sorted(dedup.values(), key=lambda x: (x['score'], len(x['sources'])), reverse=True)
    output = []
    for row in ordered[:limit]:
        evidence_score = min(
            100,
            max(20, row['score']) +
            min(20, len(row['sources']) * 4) +
            min(12, len(row['snippets']) * 2)
        )
        level = 'High' if evidence_score >= 75 else 'Medium' if evidence_score >= 45 else 'Low'
        output.append({
            'name': row['name'],
            'score': evidence_score,
            'evidence_level': level,
            'evidence_summary': f"Matched {role} search evidence for {industry}" + (f" in/near {location}." if role == 'local' else '.'),
            'sources': row['sources'][:3],
        })
    return output


def _entity_tokens(name: str) -> list[str]:
    return [t for t in _tokens(name) if len(t) >= 3]


def evidence_visibility_score(items: list[dict], name: str, official_domain: str = "") -> int:
    """Score observable live-web visibility; never represents market share."""
    target = _norm(name)
    tokens = _entity_tokens(name)
    if not target and not tokens:
        return 0

    matched = []
    for item in items:
        corpus = _norm(" ".join([
            item.get("title", ""), item.get("body", ""), item.get("href", "")
        ]))
        exact = target in corpus if target else False
        token_hits = sum(1 for token in tokens if token in corpus)
        if exact or (tokens and token_hits >= max(1, len(tokens) // 2)):
            matched.append(item)

    if not matched:
        return 0

    unique_sources = {
        urlparse(x.get("href", "")).netloc.lower().replace("www.", "")
        for x in matched if x.get("href")
    }
    unique_queries = {
        _norm(x.get("query", "")) for x in matched if _norm(x.get("query", ""))
    }

    score = 20
    score += min(30, len(matched) * 3)
    score += min(20, len(unique_sources) * 4)
    score += min(20, len(unique_queries) * 4)

    domain = _norm(official_domain).replace("https://", "").replace("http://", "").strip("/")
    if domain and any(domain in _norm(x.get("href", "")) for x in matched):
        score += 10

    return min(100, score)


def candidate_verification(raw: str, candidate: str, industry: str, location: str, role: str, target_name: str = "") -> dict | None:
    """Verify one discovered company against fresh exact-name search evidence."""
    candidate_norm = _norm(candidate)
    if not candidate_norm or candidate_norm in {_norm(target_name), ""}:
        return None

    items = parse_search_results(raw)
    matching = []
    for item in items:
        if _is_noise(item):
            continue
        title = _norm(item.get("title", ""))
        body = _norm(item.get("body", ""))
        href = _norm(item.get("href", ""))
        evidence = " ".join([title, body, href])
        exact = candidate_norm in evidence
        if not exact:
            # Multi-word names sometimes appear without punctuation/casing changes.
            candidate_parts = _tokens(candidate)
            exact = len(candidate_parts) >= 2 and sum(p in evidence for p in candidate_parts) >= max(2, len(candidate_parts) - 1)
        if not exact:
            continue

        industry_terms = expand_industry_terms(industry)
        industry_hits = sum(1 for term in industry_terms if term in evidence)

        company_signals = {
            "company", "corporation", "technologies", "technology", "solutions",
            "systems", "software", "consulting", "services", "pvt ltd", "private limited",
            "limited", "inc", "llc", "corp", "founded", "headquarters", "about us",
            "our services", "contact us", "linkedin"
        }
        company_identity_hits = sum(1 for signal in company_signals if signal in evidence)
        if company_identity_hits == 0:
            continue

        if role == "local":
            location_terms = expand_location_terms(location)
            location_hits = sum(1 for term in location_terms if term in evidence)
            if industry_hits == 0 or location_hits == 0:
                continue
        else:
            if industry_hits == 0:
                continue

        matching.append(item)

    if not matching:
        return None

    domains = []
    for item in matching:
        host = urlparse(item.get("href", "")).netloc.lower().replace("www.", "")
        if host and host not in domains and not any(d in host for d in DIRECTORY_DOMAINS):
            domains.append(host)

    if len(matching) < 2 or len(domains) < 1:
        return None

    source_urls = []
    for item in matching:
        href = item.get("href", "")
        if href and href not in source_urls:
            source_urls.append(href)

    score = min(100, 50 + min(20, len(matching) * 5) + min(20, len(domains) * 5))
    return {
        "name": candidate,
        "verification_score": score,
        "evidence_level": "High" if score >= 80 else "Medium",
        "evidence_summary": f"Fresh exact-name search found {len(matching)} relevant result(s) across {len(domains)} source domain(s) supporting this {role} company.",
        "sources": source_urls[:5],
    }

def target_evidence(raw: str, name: str, industry: str, location: str) -> dict:
    items = parse_search_results(raw)
    relevant = [x for x in items if _match_score(x, industry, location, 'target', name) >= 35]
    sources = []
    for item in relevant:
        if item.get('href') and item['href'] not in sources:
            sources.append(item['href'])
    score = evidence_visibility_score(items, name)
    level = 'High' if score >= 75 else 'Medium' if score >= 45 else 'Low' if score > 0 else 'None'
    return {
        'name': name,
        'score': score,
        'evidence_level': level,
        'evidence_summary': f'Live search produced {len(relevant)} relevant target result(s) from {len(sources)} source URL(s).',
        'sources': sources[:5],
    }

def summarize_fallback(name: str, industry: str, location: str, target_raw: str, local_raw: str, global_raw: str) -> dict:
    target = target_evidence(target_raw, name, industry, location)
    local = rank_candidates(local_raw, industry, location, 'local', name, 5)
    global_ = rank_candidates(global_raw, industry, location, 'global', name, 5)
    return {
        'target': target,
        'local_competitors': local,
        'market_leaders': global_,
        'insight_summary': (
            f'Live research identified {len(local)} locally relevant competitor candidates and {len(global_)} global candidates for {name}. '
            'Candidates were filtered for industry relevance and obvious non-business results; scores are digital-visibility evidence estimates.'
        ),
        'research_coverage': {
            'status': 'live_ddgs', 'provider': 'DDGS',
            'target_results': len(parse_search_results(target_raw)),
            'local_candidates': len(local), 'global_candidates': len(global_),
        },
    }
