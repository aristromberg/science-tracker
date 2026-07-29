"""PubMed search via NCBI E-utilities (Biopython Entrez)."""

import logging
import os

from Bio import Entrez

logger = logging.getLogger(__name__)


def _configure_entrez():
    email = os.environ.get("PUBMED_EMAIL")
    if not email:
        raise RuntimeError(
            "PUBMED_EMAIL environment variable is required by NCBI E-utilities "
            "(set it in .env or as a GitHub Actions secret)."
        )
    Entrez.email = email
    api_key = os.environ.get("PUBMED_API_KEY")
    if api_key:
        Entrez.api_key = api_key


def search_query(query: str, lookback_days: int, max_results: int) -> list[dict]:
    """Run one PubMed query and return article dicts (pmid, title, abstract, url, journal, source)."""
    _configure_entrez()

    with Entrez.esearch(
        db="pubmed",
        term=query,
        reldate=lookback_days,
        datetype="pdat",
        retmax=max_results,
        sort="pub date",
    ) as handle:
        search_results = Entrez.read(handle)

    pmids = search_results.get("IdList", [])
    if not pmids:
        return []

    with Entrez.efetch(db="pubmed", id=pmids, rettype="abstract", retmode="xml") as handle:
        records = Entrez.read(handle)

    articles = []
    for record in records.get("PubmedArticle", []):
        try:
            articles.append(_parse_record(record, query))
        except (KeyError, IndexError) as exc:
            logger.warning("Skipping malformed PubMed record: %s", exc)
    return articles


def _parse_record(record: dict, query: str) -> dict:
    medline = record["MedlineCitation"]
    article = medline["Article"]
    pmid = str(medline["PMID"])

    title = str(article.get("ArticleTitle", "")).strip()

    abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
    abstract = " ".join(str(part) for part in abstract_parts).strip()

    journal = str(article.get("Journal", {}).get("Title", "")).strip()

    return {
        "id": f"pmid:{pmid}",
        "source": "pubmed",
        "matched_query": query,
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def search_all(queries: list[str], lookback_days: int, max_results_per_query: int) -> list[dict]:
    """Run all configured PubMed queries and return the merged article list (not deduped)."""
    all_articles = []
    for query in queries:
        try:
            all_articles.extend(search_query(query, lookback_days, max_results_per_query))
        except Exception:
            logger.exception("PubMed search failed for query %r", query)
    return all_articles
