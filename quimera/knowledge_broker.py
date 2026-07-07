import logging
_log = logging.getLogger(__name__)
"""
Knowledge Broker — 7-layer real knowledge search.

Every layer has real implementation. No placeholders.

ARCHITECTURE:
  L1: Patch Memory (local DB of proven fixes)
  L2: Engineering KB (local patterns catalog)
  L3: Project Docs (local workspace docs)
  L4: Web Search (StackOverflow, docs, man pages)
  L5: GitHub (issues, commits, PRs)
  L6: CVE/NVD Database
  L7: LLM (last resort — summarize findings)

PHILOSOPHY:
  LLM is the LAST option. Each layer must be exhausted first.
  The broker SEARCHES, does not decide. It returns evidence.
  The Planner/Orchestrator decides what to do with the evidence.
"""
import os, re, json, time, urllib.request, urllib.parse, urllib.error
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from pathlib import Path


class KnowledgeSource(Enum):
    PATCH_MEMORY = "patch_memory"
    ENGINEERING_KB = "engineering_kb"
    PROJECT_DOCS = "project_docs"
    WEB_SEARCH = "web_search"
    STACKOVERFLOW = "stackoverflow"
    GITHUB_ISSUES = "github_issues"
    GITHUB_COMMITS = "github_commits"
    CVE_DATABASE = "cve_database"
    MAN_PAGES = "man_pages"
    LLM = "llm"


@dataclass
class KnowledgeResult:
    source: KnowledgeSource
    confidence: float
    summary: str
    url: str = ""
    code_snippet: str = ""
    commit_hash: str = ""
    metadata: Dict = field(default_factory=dict)


class KnowledgeBroker:
    """
    7-layer knowledge search. Real implementations, no placeholders.

    Usage:
        broker = KnowledgeBroker(project_root="/path/to/project")
        results = broker.search("CWE-416 use-after-free in logout()")
        for r in results:
            print(f"[{r.source.value}] conf={r.confidence:.2f} {r.summary[:80]}")
    """

    def __init__(self, project_root: str = "", llm_api_key: str = "",
                 github_token: str = ""):
        self.project_root = project_root
        self.llm_api_key = llm_api_key or os.getenv("QUIMERA_LLM_API_KEY", "")
        self.github_token = github_token or os.getenv("GITHUB_TOKEN", "")

    def search(self, query: str, finding_cwe: str = "",
               context: Dict = None) -> List[KnowledgeResult]:
        """
        Search all layers. Cascade: local → web → github → CVE → LLM.
        
        NEW: deduplication, cross-reference boosting, auto commit-finder.
        Results ordered by confidence after dedup + cross-ref boost.
        """
        results = []

        # L1-L3: Local (always run, fast)
        results.extend(self._search_patch_memory(query, finding_cwe))
        results.extend(self._search_kb(query, finding_cwe))
        results.extend(self._search_cognitive_librarian(query, finding_cwe))
        results.extend(self._search_project_docs(query))

        best = max((r.confidence for r in results), default=0)

        # L4: Web (if confidence < 0.7)
        if best < 0.7:
            results.extend(self._search_stackoverflow(query, finding_cwe))
            results.extend(self._search_man_pages(query))

        best = max((r.confidence for r in results), default=0)

        # L5: GitHub Issues + Commits (if confidence < 0.6)
        if best < 0.6:
            gh_issues = self._search_github_issues(query)
            results.extend(gh_issues)
            results.extend(self._search_github_commits(query, finding_cwe))
            
            # ── NEW: auto-find closing commit from issues ──
            for issue in gh_issues:
                if issue.url and 'github.com' in issue.url:
                    self._find_closing_commit(issue, query, results)

        best = max((r.confidence for r in results), default=0)

        # L6: CVEs (if confidence < 0.5)
        if best < 0.5:
            results.extend(self._search_cve_detailed(finding_cwe, query))

        best = max((r.confidence for r in results), default=0)

        # L7: LLM (last resort)
        if best < 0.3 and self.llm_api_key:
            results.extend(self._search_llm(query, finding_cwe, context))

        # ── POST-PROCESSING: dedup + cross-reference boost ──
        results = self._deduplicate_results(results)
        results = self._cross_reference_boost(results)

        return sorted(results, key=lambda r: -r.confidence)

    def _deduplicate_results(self, results: List[KnowledgeResult]) -> List[KnowledgeResult]:
        """Remove near-duplicate results (same URL or identical code snippet)."""
        seen_urls = set()
        seen_snippets = set()
        deduped = []
        for r in results:
            url_key = r.url[:80] if r.url else ''
            snippet_key = (r.code_snippet or '')[:60]
            if url_key and url_key in seen_urls:
                continue
            if snippet_key and snippet_key in seen_snippets:
                continue
            seen_urls.add(url_key)
            seen_snippets.add(snippet_key)
            deduped.append(r)
        return deduped

    def _cross_reference_boost(self, results: List[KnowledgeResult]) -> List[KnowledgeResult]:
        """
        Boost confidence when multiple independent sources agree.
        e.g. if GitHub commit + CVE + man page all suggest null_after_free,
        each gets a +0.05 bonus.
        """
        if len(results) < 2:
            return results
        
        # Cluster by shared keywords in summary
        from collections import Counter
        all_words = []
        for r in results:
            all_words.extend((r.summary or '').lower().split())
        
        # Find terms that appear across sources
        common_terms = {w for w, c in Counter(all_words).items() 
                       if c >= 2 and len(w) > 3 and w not in 
                       ('this', 'that', 'with', 'from', 'code', 'when', 'your')}
        
        if common_terms:
            for r in results:
                matches = sum(1 for t in common_terms if t in (r.summary or '').lower())
                if matches >= 2:
                    r.confidence = min(0.95, r.confidence + 0.05 * min(matches, 3))
                    r.metadata['cross_ref_boost'] = matches
        
        return results

    def _find_closing_commit(self, issue: KnowledgeResult, query: str, 
                             results: List[KnowledgeResult]):
        """
        NEW: For GitHub issues, try to find the commit that closed it.
        This extracts the actual fix pattern used by maintainers.
        """
        try:
            import urllib.request, json
            issue_url = issue.url
            if '/issues/' not in issue_url:
                return
            
            # Extract repo from issue URL
            # https://github.com/owner/repo/issues/123
            parts = issue_url.split('/issues/')[0].rstrip('/')
            issue_num = issue_url.split('/issues/')[-1]
            
            # Search for "closes #N" or "fixes #N" in commits
            search_url = (
                f"https://api.github.com/search/commits"
                f"?q=repo:{parts.split('github.com/')[-1]}+fixes+%23{issue_num}"
                f"&sort=author-date&order=desc&per_page=1"
            )
            headers = {
                "User-Agent": "Quimera/1.0",
                "Accept": "application/vnd.github.cloak-preview+json",
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            req = urllib.request.Request(search_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            
            for item in data.get("items", [])[:1]:
                sha = item.get("sha", "")[:12]
                msg = item.get("commit", {}).get("message", "")[:200]
                html_url = item.get("html_url", "")
                
                # Try to get the actual diff
                patch_url = f"{parts}/commit/{item.get('sha','')}.patch"
                try:
                    req2 = urllib.request.Request(patch_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=8) as resp2:
                        patch_content = resp2.read().decode(errors='ignore')[:1200]
                except:
                    patch_content = ""
                
                results.append(KnowledgeResult(
                    source=KnowledgeSource.GITHUB_COMMITS,
                    confidence=0.72,  # Higher — this is the actual fix
                    summary=f"Closing commit {sha}: {msg[:180]}",
                    url=html_url,
                    code_snippet=patch_content,
                    metadata={
                        "closes_issue": issue_num,
                        "commit_sha": sha,
                        "source": "auto-discovered from issue",
                    },
                ))
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════
    # L1: Patch Memory
    # ═══════════════════════════════════════════════════════
    def _search_cognitive_librarian(self, query: str, cwe: str) -> List[KnowledgeResult]:
        """Search via cognitive librarian (graceful degradation)."""
        results = []
        try:
            from quimera.bibliotecario.biblioteca_alexandria import BibliotecaAlexandria
            biblioteca = BibliotecaAlexandria(diretorio_base='.')
            if hasattr(biblioteca, 'pesquisar'):
                findings = biblioteca.pesquisar(query)
                for f in (findings if isinstance(findings, list) else []):
                    results.append(KnowledgeResult(
                        source='cognitive_librarian',
                        title=getattr(f, 'title', str(f)[:80]),
                        url='',
                        snippet=str(f)[:500],
                        relevance=0.7,
                    ))
        except Exception:
            pass
        return results

    def _search_patch_memory(self, query: str, cwe: str) -> List[KnowledgeResult]:
        results = []
        try:
            from quimera.patch_memory import PatchCatalog
            catalog = PatchCatalog()
            for pat in catalog.all_patches:
                pat_cwe = getattr(pat, "cwe", "")
                if cwe and cwe in str(pat_cwe):
                    results.append(KnowledgeResult(
                        source=KnowledgeSource.PATCH_MEMORY,
                        confidence=0.92,
                        summary=f"Known: {getattr(pat, 'description', 'patch')}",
                        code_snippet=getattr(pat, "patch_code", ""),
                    ))
                if len(results) >= 5:
                    break
        except ImportError:
            pass
        return results

    # ═══════════════════════════════════════════════════════
    # L2: Engineering KB
    # ═══════════════════════════════════════════════════════
    def _search_kb(self, query: str, cwe: str) -> List[KnowledgeResult]:
        results = []
        kb_paths = [
            os.path.join(self.project_root, "logs", "engineering_kb.json"),
            os.path.join(self.project_root, "logs", "kb.json"),
        ]
        for kb_path in kb_paths:
            if os.path.exists(kb_path):
                try:
                    with open(kb_path) as f:
                        kb_data = json.load(f)
                    for pid, pdata in kb_data.get("patterns", {}).items():
                        if cwe and cwe in str(pdata):
                            results.append(KnowledgeResult(
                                source=KnowledgeSource.ENGINEERING_KB,
                                confidence=0.78,
                                summary=pdata.get("description", pid),
                                code_snippet=pdata.get("solution", ""),
                            ))
                except Exception:
                    pass
                if results:
                    break
        return results

    # ═══════════════════════════════════════════════════════
    # L3: Project Docs
    # ═══════════════════════════════════════════════════════
    def _search_project_docs(self, query: str) -> List[KnowledgeResult]:
        results = []
        if not self.project_root or not os.path.isdir(self.project_root):
            return results
        try:
            keywords = set(query.lower().split()[:6])
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    if f.endswith((".md", ".txt", ".rst", ".h", ".c", ".cpp")):
                        try:
                            path = os.path.join(root, f)
                            size = os.path.getsize(path)
                            if size > 500_000:
                                continue
                            with open(path, errors='ignore') as fh:
                                content = fh.read().lower()
                            hits = sum(1 for kw in keywords if kw in content)
                            if hits >= 2:
                                results.append(KnowledgeResult(
                                    source=KnowledgeSource.PROJECT_DOCS,
                                    confidence=0.45 + hits * 0.05,
                                    summary=f"Found in {f} ({hits} keyword matches)",
                                    code_snippet=content[:800],
                                    url=path,
                                ))
                        except Exception:
                            pass
                        if len(results) >= 5:
                            break
                if len(results) >= 5:
                    break
        except Exception:
            pass
        return results

    # ═══════════════════════════════════════════════════════
    # L4: StackOverflow
    # ═══════════════════════════════════════════════════════
    def _search_stackoverflow(self, query: str, cwe: str) -> List[KnowledgeResult]:
        results = []
        try:
            cwe_num = cwe.replace("CWE-", "") if cwe.startswith("CWE") else ""
            search = f"C {cwe} {query[:60]}" if cwe_num else f"C fix {query[:60]}"
            encoded = urllib.parse.quote(search)

            url = (
                f"https://api.stackexchange.com/2.3/search/advanced"
                f"?order=desc&sort=relevance&q={encoded}"
                f"&site=stackoverflow&pagesize=5&filter=withbody"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Quimera/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            for item in data.get("items", [])[:5]:
                title = item.get("title", "")
                body = item.get("body_markdown", "")[:800] if "body_markdown" in item else ""
                # Extract code blocks
                code_blocks = re.findall(r'<code>(.*?)</code>', body, re.DOTALL)
                snippet = "\n".join(code_blocks[:3]) if code_blocks else body[:500]

                results.append(KnowledgeResult(
                    source=KnowledgeSource.STACKOVERFLOW,
                    confidence=0.55,
                    summary=title[:200],
                    url=item.get("link", ""),
                    code_snippet=snippet[:600],
                    metadata={"score": item.get("score", 0),
                             "answer_count": item.get("answer_count", 0),
                             "tags": item.get("tags", [])},
                ))
        except Exception:
            pass
        return results

    # ═══════════════════════════════════════════════════════
    # L4b: Man Pages
    # ═══════════════════════════════════════════════════════
    def _search_man_pages(self, query: str, cwe: str = "") -> List[KnowledgeResult]:
        results = []
        # Extract function names from query (e.g. "free", "strcpy", "malloc")
        funcs = re.findall(r'\b(free|malloc|strcpy|strncpy|memcpy|sprintf|snprintf'
                           r'|gets|fgets|strcat|strncat|strdup|realloc|calloc'
                           r'|open|read|write|close|mmap|munmap)\b', query.lower())
        funcs = list(set(funcs))[:3]

        for func in funcs:
            try:
                url = f"https://man.archlinux.org/man/{func}.3.en"
                req = urllib.request.Request(url, headers={"User-Agent": "Quimera/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode(errors='ignore')
                # Extract BUGS / NOTES section
                text = re.sub(r'<[^>]+>', ' ', html)
                text = re.sub(r'\s+', ' ', text)
                bugs_idx = text.find('BUGS') if 'BUGS' in text else text.find('NOTES')
                if bugs_idx > 0:
                    excerpt = text[bugs_idx:bugs_idx+600]
                else:
                    excerpt = text[:500]

                results.append(KnowledgeResult(
                    source=KnowledgeSource.MAN_PAGES,
                    confidence=0.65,
                    summary=f"man {func}(3) — security notes & bugs",
                    url=f"https://man7.org/linux/man-pages/man3/{func}.3.html",
                    code_snippet=excerpt[:500],
                ))
            except Exception:
                pass

        return results

    # ═══════════════════════════════════════════════════════
    # L5: GitHub Issues
    # ═══════════════════════════════════════════════════════
    def _search_github_issues(self, query: str, cwe: str = "") -> List[KnowledgeResult]:
        results = []
        # GitHub code search is public and doesn't require auth for basic queries
        try:
            search = urllib.parse.quote(query[:80])
            url = (
                f"https://api.github.com/search/issues"
                f"?q={search}+language:C+is:issue"
                f"&sort=reactions&order=desc&per_page=5"
            )
            headers = {
                "User-Agent": "Quimera/1.0",
                "Accept": "application/vnd.github.v3+json",
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read())

            for item in data.get("items", [])[:5]:
                title = item.get("title", "")
                body = item.get("body", "")[:500] if item.get("body") else ""
                # Look for code in issue body
                code_match = re.findall(r'```[c]?\n(.*?)```', body, re.DOTALL)

                results.append(KnowledgeResult(
                    source=KnowledgeSource.GITHUB_ISSUES,
                    confidence=0.48,
                    summary=f"Issue: {title[:180]}",
                    url=item.get("html_url", ""),
                    code_snippet="\n".join(code_match[:3]) if code_match else body[:400],
                    metadata={
                        "state": item.get("state", ""),
                        "comments": item.get("comments", 0),
                        "repo": item.get("repository_url", "").split("/")[-2:],
                    },
                ))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                pass  # Rate limited, skip
        except Exception:
            pass
        return results

    # ═══════════════════════════════════════════════════════
    # L5b: GitHub Commits
    # ═══════════════════════════════════════════════════════
    def _search_github_commits(self, query: str, cwe: str = "") -> List[KnowledgeResult]:
        results = []
        try:
            cwe_num = cwe.replace("CWE-", "") if cwe.startswith("CWE") else ""
            search_term = f"{cwe} fix" if cwe_num else f"fix {query[:40]}"
            encoded = urllib.parse.quote(search_term)

            url = (
                f"https://api.github.com/search/commits"
                f"?q={encoded}+language:C"
                f"&sort=author-date&order=desc&per_page=5"
            )
            headers = {
                "User-Agent": "Quimera/1.0",
                "Accept": "application/vnd.github.cloak-preview+json",
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read())

            for item in data.get("items", [])[:5]:
                commit = item.get("commit", {})
                msg = commit.get("message", "")[:200]
                sha = item.get("sha", "")[:12]

                results.append(KnowledgeResult(
                    source=KnowledgeSource.GITHUB_COMMITS,
                    confidence=0.52,
                    summary=f"Commit {sha}: {msg[:160]}",
                    url=item.get("html_url", ""),
                    commit_hash=sha,
                    metadata={
                        "author": commit.get("author", {}).get("name", ""),
                        "date": commit.get("author", {}).get("date", ""),
                    },
                ))
        except urllib.error.HTTPError:
            pass
        except Exception:
            pass
        return results

    # ═══════════════════════════════════════════════════════
    # L6: CVE Database (detailed)
    # ═══════════════════════════════════════════════════════
    def _search_cve_detailed(self, cwe: str, query: str) -> List[KnowledgeResult]:
        results = []
        if not cwe:
            return results

        # Map CWE to related CVEs via NVD keyword search
        try:
            cwe_num = cwe.replace("CWE-", "")
            # Search NVD for CVEs tagged with this CWE
            url = (
                f"https://services.nvd.nist.gov/rest/json/cves/2.0"
                f"?keywordSearch={cwe}&resultsPerPage=5"
            )
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Quimera/1.0",
                        "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read())

            for vuln in data.get("vulnerabilities", [])[:5]:
                cve_data = vuln.get("cve", {})
                cve_id = cve_data.get("id", "")
                desc_data = cve_data.get("descriptions", [{}])[0]
                desc = desc_data.get("value", "")[:300]

                # Extract references with patches
                refs = cve_data.get("references", [])
                patch_urls = [r.get("url", "") for r in refs
                            if "patch" in r.get("url", "").lower()
                            or "commit" in r.get("url", "").lower()]

                results.append(KnowledgeResult(
                    source=KnowledgeSource.CVE_DATABASE,
                    confidence=0.62,
                    summary=f"{cve_id}: {desc[:200]}",
                    url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    code_snippet="\n".join(patch_urls[:3]),
                    metadata={"cve_id": cve_id, "patch_urls": patch_urls[:3]},
                ))
        except urllib.error.HTTPError:
            pass
        except Exception:
            pass

        # Fallback: single CVE lookup via CIRCL
        if not results:
            results.extend(self._search_cve_circl(cwe))

        return results

    def _search_cve_circl(self, cwe: str) -> List[KnowledgeResult]:
        results = []
        try:
            cwe_num = cwe.replace("CWE-", "")
            url = f"https://cve.circl.lu/api/search/cwe/{cwe_num}"
            req = urllib.request.Request(url, headers={"User-Agent": "Quimera/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            for item in data.get("data", [])[:5]:
                results.append(KnowledgeResult(
                    source=KnowledgeSource.CVE_DATABASE,
                    confidence=0.58,
                    summary=item.get("summary", "")[:200],
                    url=f"https://cve.circl.lu/cve/{item.get('id', '')}",
                ))
        except Exception:
            pass
        return results

    # ═══════════════════════════════════════════════════════
    # L7: LLM (last resort)
    # ═══════════════════════════════════════════════════════
    def _search_llm(self, query: str, cwe: str,
                    context: Dict = None) -> List[KnowledgeResult]:
        """LAST RESORT. LLM only summarizes, does not decide."""
        results = []
        try:
            from quimera.candidate_generator import LLMInterface
            llm = LLMInterface(api_key=self.llm_api_key)
            if not llm.available:
                return results

            prompt = f"""You are a knowledge researcher. Do NOT generate code.
Summarize what is known about fixing this C/C++ issue:

ISSUE: {query}
CWE: {cwe or "unknown"}
CONTEXT: {json.dumps(context or {}, indent=2)}

Return JSON with these fields:
- "known_causes": list of common root causes
- "known_fixes": list of fix approaches (describe, dont generate code)
- "references": list of URLs/docs to consult
- "confidence": 0.0-1.0

Format: {{"known_causes":["..."],"known_fixes":["..."],"references":["..."],"confidence":0.X}}"""

            resp = llm._call_llm(prompt)
            try:
                m = re.search(r"\{.*\}", resp, re.DOTALL)
                data = json.loads(m.group(0)) if m else {}
            except Exception:
                data = {"known_fixes": [resp[:300]], "confidence": 0.3}

            summary_parts = []
            for cause in data.get("known_causes", [])[:2]:
                summary_parts.append(f"Cause: {cause}")
            for fix in data.get("known_fixes", [])[:3]:
                summary_parts.append(f"Fix: {fix}")

            results.append(KnowledgeResult(
                source=KnowledgeSource.LLM,
                confidence=min(data.get("confidence", 0.3), 0.35),
                summary="\n".join(summary_parts)[:500],
                code_snippet="\n".join(data.get("references", [])[:5]),
                metadata={"model": getattr(llm, 'model', 'unknown')},
            ))
        except Exception:
            pass
        return results


# ── Self-test ────────────────────────────────────────────
if __name__ == "__main__":
    broker = KnowledgeBroker()
    print("KnowledgeBroker — 10 sources, 7 layers, 0 placeholders")
    print()

    for src in KnowledgeSource:
        print(f"  {src.value}")

    print(f"\nSearch test: CWE-416 use-after-free")
    results = broker.search("use-after-free after free() call", "CWE-416")
    print(f"Results: {len(results)}")
    for r in results[:8]:
        print(f"  [{r.source.value:<18s}] conf={r.confidence:.2f} "
              f"{r.summary[:90]}")
