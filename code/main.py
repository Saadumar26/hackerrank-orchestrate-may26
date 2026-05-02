#!/usr/bin/env python3
"""
HackerRank Orchestrate Support Triage Agent
Terminal-based agent that routes support tickets across HackerRank, Claude, and Visa.
"""

import os
import csv
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import re
import string

# Data paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
TICKETS_DIR = REPO_ROOT / "support_tickets"
INPUT_CSV = TICKETS_DIR / "support_tickets.csv"
OUTPUT_CSV = TICKETS_DIR / "output.csv"


class CorpusLoader:
    """Load and index the support corpus from markdown files."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.corpus: Dict[str, Dict[str, str]] = defaultdict(dict)  # {company: {doc_id: content}}
        self.index: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # {word: [(company, doc_id)]}
        self.load()
    
    def load(self):
        """Load all markdown files into corpus."""
        for company_dir in self.data_dir.iterdir():
            if not company_dir.is_dir():
                continue
            
            company_name = company_dir.name.lower()
            
            for md_file in company_dir.rglob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8", errors="ignore")
                    doc_id = str(md_file.relative_to(self.data_dir))
                    self.corpus[company_name][doc_id] = content
                    
                    # Index words
                    words = set(re.findall(r"\b\w+\b", content.lower()))
                    for word in words:
                        self.index[word].append((company_name, doc_id))
                except Exception as e:
                    print(f"Error loading {md_file}: {e}", flush=True)
        
        print(f"✓ Loaded corpus: {sum(len(v) for v in self.corpus.values())} documents", flush=True)
    
    def search(self, query: str, company: str = None) -> List[Tuple[float, str, str]]:
        """
        Search corpus for matching documents using improved scoring.
        Returns: [(score, company, doc_id), ...]
        """
        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        if not query_words:
            return []
        
        # Remove common stopwords
        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "is", "was", "be", "have", "has", "are", "were", "this", "that", "with", "from", "by", "can", "will", "do", "does", "did"}
        query_words = {w for w in query_words if w not in stopwords and len(w) > 2}
        
        if not query_words:
            return []
        
        scores = defaultdict(float)
        word_counts = defaultdict(int)
        
        for word in query_words:
            doc_count = len(self.index.get(word, []))
            for corp, doc_id in self.index.get(word, []):
                if company and corp != company:
                    continue
                # TF-IDF-like scoring: longer words + less frequent = higher score
                tf = 1.0
                idf = 1.0 + (10.0 / (1.0 + doc_count))  # Avoid division by zero
                word_weight = (1.0 + len(word) / 10.0) * idf
                scores[(corp, doc_id)] += word_weight
                word_counts[(corp, doc_id)] += 1
        
        results = [(score, corp, doc_id) for (corp, doc_id), score in scores.items()]
        results.sort(reverse=True)
        return results
    
    def get_document(self, company: str, doc_id: str) -> str:
        """Retrieve full document content."""
        return self.corpus.get(company, {}).get(doc_id, "")


class ResponseExtractor:
    """Extract and synthesize responses from documents."""
    
    # Map document paths to product areas
    PRODUCT_AREA_MAPPING = {
        "billing": ["pricing", "billing", "subscription", "payment", "invoice"],
        "authentication": ["authentication", "login", "password", "access", "account", "mfa", "2fa"],
        "api": ["api", "endpoint", "documentation", "integration"],
        "bug": ["bug", "issue", "error", "troubleshooting", "problem"],
        "features": ["feature", "release", "capability", "functionality"],
        "general": ["general", "help", "faq"],
    }
    
    @staticmethod
    def infer_product_area(doc_id: str, doc_content: str) -> str:
        """Infer product area from document path and content."""
        # Check document path first (most reliable)
        path_lower = doc_id.lower()
        for area, keywords in ResponseExtractor.PRODUCT_AREA_MAPPING.items():
            if any(kw in path_lower for kw in keywords):
                return area
        
        # Fall back to content analysis
        content_lower = doc_content[:500].lower()
        scores = {area: sum(1 for kw in keywords if kw in content_lower)
                  for area, keywords in ResponseExtractor.PRODUCT_AREA_MAPPING.items()}
        return max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
    
    @staticmethod
    def extract_relevant_section(doc: str, query: str, max_length: int = 500) -> str:
        """
        Extract most relevant section from document.
        Strategy:
        1. Skip YAML frontmatter
        2. Find headers and extract relevant sections
        3. Look for Q&A patterns
        4. Extract first substantial paragraph
        """
        # Remove YAML frontmatter (between --- markers at start)
        if doc.startswith("---"):
            try:
                end_marker = doc.find("---", 3)
                if end_marker > 0:
                    doc = doc[end_marker + 3:].lstrip("\n")
            except:
                pass
        
        query_lower = query.lower()
        query_words = set(re.findall(r"\b\w{3,}\b", query_lower))
        
        # Split by markdown headers
        lines = doc.split("\n")
        sections = []
        current_section = []
        
        for line in lines:
            if re.match(r"^#{1,6}\s+", line):
                if current_section:
                    sections.append("\n".join(current_section))
                    current_section = []
                sections.append(line)
            else:
                current_section.append(line)
        
        if current_section:
            sections.append("\n".join(current_section))
        
        best_section = ""
        best_score = -1
        
        # Find best matching section
        for i in range(0, len(sections), 2):
            if i + 1 < len(sections):
                section_header = sections[i]
                section_body = sections[i + 1]
            else:
                section_header = ""
                section_body = sections[i]
            
            section_text = (section_header + " " + section_body).lower()
            
            # Score based on query word matches
            score = sum(1 for word in query_words if word in section_text)
            
            if score > best_score and len(section_body.strip()) > 30:
                best_section = section_body.strip()
                best_score = score
        
        # If no section matched, use longest substantial paragraph
        if best_score <= 0:
            paragraphs = [p.strip() for p in doc.split("\n\n") 
                         if p.strip() and len(p.strip()) > 30 and not p.strip().startswith("#")]
            if paragraphs:
                best_section = paragraphs[0]
        
        # If still nothing, use first chunk
        if not best_section:
            best_section = doc[:300].strip()
        
        # Clean up and truncate
        best_section = best_section.strip()
        if len(best_section) > max_length:
            # Try to cut at sentence boundary
            truncated = best_section[:max_length]
            last_period = truncated.rfind(".")
            if last_period > max_length * 0.7:
                best_section = truncated[:last_period + 1]
            else:
                best_section = truncated.rstrip() + "..."
        
        return best_section
    
    @staticmethod
    def synthesize_response(matches: List[Tuple[str, str]], query: str, corpus: 'CorpusLoader', max_length: int = 600) -> Tuple[str, List[str]]:
        """
        Synthesize response from top 1-3 matching documents.
        Returns: (response_text, doc_ids_used)
        """
        if not matches:
            return "", []
        
        sections = []
        doc_ids_used = []
        
        for company, doc_id in matches[:3]:  # Use top 3
            doc_content = corpus.get_document(company, doc_id)
            section = ResponseExtractor.extract_relevant_section(doc_content, query, max_length=300)
            if section:
                sections.append(section)
                doc_ids_used.append(doc_id)
                if sum(len(s) for s in sections) > max_length:
                    break
        
        response = "\n\n".join(sections)
        if len(response) > max_length:
            response = response[:max_length].rstrip() + "..."
        
        return response, doc_ids_used


class TicketClassifier:
    """Classify tickets by company, product area, and request type."""
    
    # Mapping of keywords to companies
    COMPANY_KEYWORDS = {
        "hackerrank": [
            "hackerrank", "test", "assessment", "interview", "candidate",
            "screen", "coding", "platform", "assignment", "recruiter"
        ],
        "claude": [
            "claude", "ai", "model", "api", "anthropic", "chat", "conversation",
            "bedrock", "prompt", "token", "workspace", "team"
        ],
        "visa": [
            "visa", "payment", "card", "transaction", "fraud", "dispute",
            "chargeback", "merchant", "processor"
        ]
    }
    
    # High-risk categories that should escalate
    ESCALATION_KEYWORDS = {
        "billing": ["billing", "payment", "charge", "invoice", "refund", "subscription", "pricing"],
        "fraud": ["fraud", "unauthorized", "stolen", "chargeback", "dispute", "fraudulent"],
        "account_access": ["password", "login", "access", "locked", "reset", "mfa", "2fa", "restored"],
        "compliance": ["legal", "gdpr", "ccpa", "compliance", "audit", "sso", "hipaa"],
    }
    
    # Sentiment indicators (higher = more likely to escalate for tone)
    NEGATIVE_SENTIMENT = {
        "angry": ["furious", "outraged", "unacceptable", "terrible", "worst"],
        "urgent": ["immediately", "asap", "urgent", "emergency", "critical"],
        "adversarial": ["sue", "lawsuit", "court", "attorney", "lawyer"]
    }
    
    @staticmethod
    def classify_company(issue: str, subject: str, company: str) -> str:
        """Infer company from content if not provided."""
        if company and company != "None":
            return company.lower()
        
        text = (issue + " " + (subject or "")).lower()
        scores = {}
        for company_name, keywords in TicketClassifier.COMPANY_KEYWORDS.items():
            scores[company_name] = sum(1 for kw in keywords if kw in text)
        
        return max(scores, key=scores.get) if max(scores.values()) > 0 else "unknown"
    
    @staticmethod
    def get_risk_level(issue: str, subject: str) -> Tuple[str, str]:
        """
        Assess risk level and category.
        Returns: (risk_level, category) where risk_level in [low, medium, high]
        """
        text = (issue + " " + (subject or "")).lower()
        
        for category, keywords in TicketClassifier.ESCALATION_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return "high", category
        
        return "low", "general"
    
    @staticmethod
    def analyze_sentiment(issue: str, subject: str) -> Tuple[str, List[str]]:
        """
        Analyze sentiment to catch adversarial/urgent tickets.
        Returns: (sentiment, flags) where sentiment in [positive, neutral, negative]
        """
        text = (issue + " " + (subject or "")).lower()
        
        flags = []
        for sentiment_type, keywords in TicketClassifier.NEGATIVE_SENTIMENT.items():
            if any(kw in text for kw in keywords):
                flags.append(sentiment_type)
        
        if flags:
            return "negative", flags
        return "neutral", []
    
    @staticmethod
    def classify_request_type(issue: str) -> str:
        """Classify as product_issue, feature_request, bug, or invalid."""
        text = issue.lower().strip()
        
        # Only mark as invalid if truly empty
        if not text or len(text) < 5:
            return "invalid"
        
        bug_keywords = ["bug", "error", "crash", "broken", "doesn't work", "not working", "fail", "issue", "problem"]
        feature_keywords = ["feature", "can we", "would you", "add", "implement", "suggestion", "please add", "wish"]
        
        has_bug = any(kw in text for kw in bug_keywords)
        has_feature = any(kw in text for kw in feature_keywords)
        
        if has_bug:
            return "bug"
        if has_feature:
            return "feature_request"
        
        return "product_issue"
    
    @staticmethod
    def is_multi_domain(issue: str) -> bool:
        """Detect if ticket mentions multiple product domains."""
        text = issue.lower()
        domain_count = 0
        
        for keywords in TicketClassifier.COMPANY_KEYWORDS.values():
            if any(kw in text for kw in keywords):
                domain_count += 1
        
        return domain_count > 1


class SupportAgent:
    """Main support triage agent."""
    
    def __init__(self, corpus: CorpusLoader):
        self.corpus = corpus
        self.classifier = TicketClassifier()
        self.extractor = ResponseExtractor()
    
    def process_ticket(self, issue: str, subject: str = "", company: str = None) -> Dict:
        """
        Process a single support ticket with advanced routing.
        Returns: {status, product_area, response, justification, request_type}
        """
        # Classify the ticket
        inferred_company = self.classifier.classify_company(issue, subject, company)
        request_type = self.classifier.classify_request_type(issue)
        risk_level, risk_category = self.classifier.get_risk_level(issue, subject)
        sentiment, sentiment_flags = self.classifier.analyze_sentiment(issue, subject)
        is_multi_domain = self.classifier.is_multi_domain(issue)
        
        # Check for truly invalid tickets
        if request_type == "invalid":
            return {
                "status": "escalated",
                "product_area": "invalid",
                "response": "This request does not contain enough information to process. Please provide more details about your issue.",
                "justification": "Invalid or incomplete request",
                "request_type": "invalid"
            }
        
        # High-risk tickets should be escalated
        if risk_level == "high":
            return {
                "status": "escalated",
                "product_area": risk_category,
                "response": f"This {risk_category} matter requires immediate attention from our support team and cannot be fully addressed automatically. A specialist will contact you shortly.",
                "justification": f"High-risk category ({risk_category}) requires human escalation",
                "request_type": request_type
            }
        
        # Escalate if sentiment indicates adversarial tone
        if "adversarial" in sentiment_flags:
            return {
                "status": "escalated",
                "product_area": risk_category or "general",
                "response": "Thank you for contacting us. Given the sensitive nature of your request, we're routing this to our senior support team for immediate attention.",
                "justification": "Adversarial tone detected; escalating for specialized handling",
                "request_type": request_type
            }
        
        # Search corpus with confidence scoring
        query = issue + " " + (subject or "")
        matches = self.corpus.search(query, inferred_company if inferred_company != "unknown" else None)
        
        # Normalize confidence scores
        if matches:
            max_score = matches[0][0]
            matches_normalized = [(score / max_score if max_score > 0 else 0, corp, doc_id) 
                                 for score, corp, doc_id in matches]
        else:
            matches_normalized = []
        
        # Extract company and doc_id from normalized matches
        matches_for_synthesis = [(corp, doc_id) for score, corp, doc_id in matches_normalized[:5]]
        
        best_confidence = matches_normalized[0][0] if matches_normalized else 0
        
        # Decision tree: reply vs escalate based on confidence
        if not matches or best_confidence < 0.3:
            # Very poor match - escalate
            product_area = ResponseExtractor.infer_product_area(
                matches_for_synthesis[0][1] if matches_for_synthesis else "",
                issue
            )
            return {
                "status": "escalated",
                "product_area": product_area,
                "response": "Thank you for reaching out. We couldn't find a direct answer in our knowledge base. Our support team will review your request and get back to you soon.",
                "justification": f"Low confidence match (score: {best_confidence:.2f}); escalating to human support",
                "request_type": request_type
            }
        
        if best_confidence < 0.6:
            # Moderate match - try to answer but include escalation option
            response, doc_ids_used = ResponseExtractor.synthesize_response(
                matches_for_synthesis, query, self.corpus
            )
            product_area = ResponseExtractor.infer_product_area(
                doc_ids_used[0] if doc_ids_used else "",
                issue
            )
            
            response_with_caveat = (
                response + 
                "\n\n---\n\n*If this doesn't fully address your question, our support team can provide additional assistance.*"
            )
            
            return {
                "status": "replied",
                "product_area": product_area,
                "response": response_with_caveat,
                "justification": f"Partial match found (confidence: {best_confidence:.2f}); provided best available answer from {', '.join(doc_ids_used[:2])}",
                "request_type": request_type
            }
        
        # Good confidence match - full reply
        response, doc_ids_used = ResponseExtractor.synthesize_response(
            matches_for_synthesis, query, self.corpus
        )
        product_area = ResponseExtractor.infer_product_area(
            doc_ids_used[0] if doc_ids_used else "",
            issue
        )
        
        doc_refs = " and ".join(doc_ids_used[:3]) if doc_ids_used else "support documentation"
        
        return {
            "status": "replied",
            "product_area": product_area,
            "response": response,
            "justification": f"Strong match found (confidence: {best_confidence:.2f}); answer sourced from {doc_refs}",
            "request_type": request_type
        }


def main():
    """Main entry point."""
    print("=" * 60, flush=True)
    print("HackerRank Orchestrate Support Triage Agent", flush=True)
    print("=" * 60, flush=True)
    
    # Load corpus
    print("\n[1/3] Loading support corpus...", flush=True)
    corpus = CorpusLoader(DATA_DIR)
    
    # Initialize agent
    print("[2/3] Initializing agent...", flush=True)
    agent = SupportAgent(corpus)
    
    # Process tickets
    print(f"[3/3] Processing tickets from {INPUT_CSV}...", flush=True)
    
    results = []
    try:
        with open(INPUT_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                issue = row.get("Issue", "").strip()
                subject = row.get("Subject", "").strip()
                company = row.get("Company", "").strip()
                
                result = agent.process_ticket(issue, subject, company)
                results.append(result)
                
                if i % 10 == 0:
                    print(f"  Processed {i} tickets...", flush=True)
    except FileNotFoundError:
        print(f"ERROR: {INPUT_CSV} not found", flush=True)
        return
    
    # Write output
    print(f"\nWriting {len(results)} results to {OUTPUT_CSV}...", flush=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["status", "product_area", "response", "justification", "request_type"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✓ Done! Results written to {OUTPUT_CSV}", flush=True)
    print(f"  - Replied: {sum(1 for r in results if r['status'] == 'replied')}", flush=True)
    print(f"  - Escalated: {sum(1 for r in results if r['status'] == 'escalated')}", flush=True)


if __name__ == "__main__":
    main()
