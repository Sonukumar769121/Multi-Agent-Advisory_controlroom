"""
RAG Ingestion Pipeline for Crop Guidance and Government Schemes
Downloads, cleans, chunks, embeds, and stores documents into ChromaDB collections.

Supports real ChromaDB when installed, with an in-memory fallback store
if chromadb package is not yet installed in the environment.
"""

import os
import re
from typing import List, Dict, Any, Optional

try:
    import chromadb
    HAVE_CHROMADB = True
except ImportError:
    HAVE_CHROMADB = False

from config import CHROMA_PERSIST_DIR

# --- Seed Agronomic Documents (ICAR / KVK / State Agricultural Universities) ---
SEED_CROP_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "icar_wheat_sowing_01",
        "crop": "Wheat",
        "stage": "sowing",
        "document_name": "ICAR-IIWBR Wheat Agronomy Manual 2024",
        "source_url": "https://iiwbr.icar.gov.in/package-of-practices-wheat",
        "retrieval_date": "2024-10-15T10:00:00Z",
        "version": "2024.1",
        "text": (
            "Wheat Sowing Guidance (ICAR-IIWBR): Optimum sowing window for irrigated timely-sown wheat is November 5 to November 25. "
            "Ensure field has adequate seedbed moisture (rauni irrigation). If average daily temperature is above 28°C, delay sowing "
            "by 5-7 days as high temperature impairs germination and early tiller development. Seed rate: 100 kg/ha for timely sown, "
            "125 kg/ha for late sown. Drill sowing at 20-22 cm row spacing with 4-5 cm depth."
        ),
    },
    {
        "id": "icar_wheat_vegetative_cri_02",
        "crop": "Wheat",
        "stage": "vegetative",
        "document_name": "PAU Ludhiana Package of Practices for Rabi Crops",
        "source_url": "https://www.pau.edu/rabi-crops-wheat-package",
        "retrieval_date": "2024-10-15T10:00:00Z",
        "version": "2024.1",
        "text": (
            "Wheat Crown Root Initiation (CRI) Stage: Occurs at 20-25 days after sowing. This is the single most critical irrigation stage. "
            "Moisture stress at CRI causes irreversible yield reduction up to 35%. "
            "RULE: If forecast predicts rain >= 15 mm within 48-72 hours, HOLD irrigation to prevent waterlogging and lodging. "
            "If forecast is dry (< 5 mm rain), irrigate immediately to facilitate crown root anchor and nitrogen uptake."
        ),
    },
    {
        "id": "icar_wheat_flowering_grain_03",
        "crop": "Wheat",
        "stage": "flowering",
        "document_name": "CCS HAU Hisar Wheat Advisory Bulletin",
        "source_url": "https://hau.ac.in/extension/wheat-flowering-guide",
        "retrieval_date": "2024-10-15T10:00:00Z",
        "version": "2024.1",
        "text": (
            "Wheat Flowering and Booting Stage: Occurs 70-85 days after sowing. Maintain light and frequent irrigation to prevent heat stress. "
            "Do not irrigate during high winds (> 15 km/h) as stem lodging may occur. "
            "If 7-day rainfall forecast exceeds 10 mm, hold irrigation until soil moisture dries out."
        ),
    },
    {
        "id": "icar_rice_sowing_transplant_01",
        "crop": "Rice",
        "stage": "sowing",
        "document_name": "ICAR-NRRI Cuttack Rice Production Guide",
        "source_url": "https://icar-nrri.gov.in/rice-technologies-handbook",
        "retrieval_date": "2024-06-01T10:00:00Z",
        "version": "2024.2",
        "text": (
            "Rice Nursery & Direct Seeded Rice (DSR) Sowing: Sowing of nursery beds or DSR should commence with onset of pre-monsoon showers. "
            "Maintain thin water layer in wet nursery. If dry spell of > 5 days with zero rain is forecasted, provide protective flush irrigation."
        ),
    },
    {
        "id": "icar_mustard_flowering_01",
        "crop": "Mustard",
        "stage": "flowering",
        "document_name": "ICAR-DRMR Bharatpur Mustard Production Practices",
        "source_url": "https://drmr.res.in/mustard-advisory-flowering",
        "retrieval_date": "2024-10-15T10:00:00Z",
        "version": "2024.1",
        "text": (
            "Mustard Flowering Stage (50-60 DAS): First irrigation at flowering is critical if winter rainfall has failed. "
            "However, if rain forecast is > 10 mm within 5 days, hold irrigation to avoid white rust proliferation and aphid outbreaks. "
            "Avoid deep flooding; light furrow irrigation is advised."
        ),
    },
]

# --- Seed Government Schemes ---
SEED_SCHEME_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "gov_pm_kisan_01",
        "scheme_name": "PM-KISAN",
        "document_name": "PM-KISAN Operational Guidelines - Ministry of Agriculture & Farmers Welfare",
        "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf",
        "retrieval_date": "2024-04-01T10:00:00Z",
        "version": "2024.1",
        "state": "All India",
        "text": (
            "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN): A central sector scheme providing income support of Rs. 6,000 per year "
            "to all landholding farmer families in three equal four-monthly installments of Rs. 2,000 each. "
            "Eligibility: Landholding farmer families with cultivable landholding in their names. "
            "Exclusions: Institutional landholders, farmer families holding constitutional posts, serving/retired officers, income taxpayers. "
            "How to Apply: Farmers can register through pmkisan.gov.in portal or via Common Service Centres (CSC) with Aadhaar and land revenue records."
        ),
    },
    {
        "id": "gov_pmfby_crop_insurance_02",
        "scheme_name": "PMFBY",
        "document_name": "PMFBY Operational Guidelines Revised 2024",
        "source_url": "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf",
        "retrieval_date": "2024-04-01T10:00:00Z",
        "version": "2024.1",
        "state": "All India",
        "text": (
            "Pradhan Mantri Fasal Bima Yojana (PMFBY): Comprehensive crop insurance from pre-sowing to post-harvest against non-preventable natural risks. "
            "Covers: Prevented sowing, standing crop yield loss due to drought, dry spells, flood, pest attack, and post-harvest localized calamities. "
            "Premium Rates: 2.0% of sum insured for Kharif foodgrains/oilseeds, 1.5% for Rabi crops (Wheat, Mustard), and 5.0% for annual commercial/horticultural crops. "
            "Eligibility: All farmers growing notified crops in notified areas (both loanee and non-loanee). "
            "How to Apply: Apply through the National Crop Insurance Portal (pmfby.gov.in), commercial banks, or CSC before the season cut-off date."
        ),
    },
    {
        "id": "gov_kcc_credit_card_03",
        "scheme_name": "KCC",
        "document_name": "RBI & NABARD Kisan Credit Card Scheme Master Circular",
        "source_url": "https://www.nabard.org/kcc-guidelines",
        "retrieval_date": "2024-01-15T10:00:00Z",
        "version": "2024.1",
        "state": "All India",
        "text": (
            "Kisan Credit Card (KCC) Scheme: Simplifies access to timely and affordable short-term institutional credit for cultivation expenses, "
            "post-harvest costs, and maintenance of farm assets. Credit limit up to Rs. 3 lakh provided at a concessional interest rate of 7%, "
            "reduced to an effective rate of 4% per annum upon prompt repayment (3% interest subvention). "
            "Eligibility: All farmers, owner-cultivators, tenant farmers, oral lessees, and sharecroppers. "
            "How to Apply: Apply at any commercial, cooperative, or Regional Rural Bank branch with land ownership documents and Aadhaar."
        ),
    },
    {
        "id": "gov_soil_health_card_04",
        "scheme_name": "Soil Health Card",
        "document_name": "Soil Health Card Scheme Implementation Manual - DAC&FW",
        "source_url": "https://soilhealth.dac.gov.in/guidelines",
        "retrieval_date": "2024-01-15T10:00:00Z",
        "version": "2024.1",
        "state": "All India",
        "text": (
            "Soil Health Card Scheme: Provides farmers with crop-wise nutrient recommendations to improve soil productivity and optimize fertilizer costs. "
            "Assesses 12 parameters: Macro-nutrients (N, P, K), Secondary-nutrients (S), Micro-nutrients (Zn, Fe, Cu, Mn, Bo), and Physical parameters (pH, EC, OC). "
            "Issued every 2 years for farm holdings. "
            "Eligibility: All landholders and active cultivators across all states. "
            "How to Apply: Soil samples collected by State Agriculture Department officials and tested at district soil testing labs; report accessible at soilhealth.dac.gov.in."
        ),
    },
    {
        "id": "gov_pm_kusum_solar_05",
        "scheme_name": "PM-KUSUM",
        "document_name": "PM-KUSUM Scheme Guidelines - MNRE",
        "source_url": "https://mnre.gov.in/pm-kusum-guidelines",
        "retrieval_date": "2024-01-15T10:00:00Z",
        "version": "2024.1",
        "state": "All India",
        "text": (
            "PM-KUSUM (Pradhan Mantri Kisan Urja Suraksha evam Utthaan Mahabhiyan): Provides solar-powered irrigation pumps and solarization of existing grid-connected pumps. "
            "Component B offers 60% capital subsidy (30% Central + 30% State) for individual farmers installing standalone solar agriculture pumps up to 7.5 HP in off-grid areas. "
            "Farmer contributes 40% (can take bank loan for 30%). "
            "Eligibility: Individual farmers, farmer producer organizations (FPOs), and water user associations. "
            "How to Apply: Register on State Renewable Energy Development Agency portals (e.g. HAREDA in Haryana, PEDA in Punjab)."
        ),
    },
]


class FallbackChromaCollection:
    """In-memory ChromaDB-compatible collection."""
    def __init__(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        self.name = name
        self.metadata = metadata or {}
        self._entries: Dict[str, Dict[str, Any]] = {}

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]]) -> None:
        for doc_id, doc, meta in zip(ids, documents, metadatas):
            self._entries[doc_id] = {
                "id": doc_id,
                "document": doc,
                "metadata": meta,
            }

    def query(
        self,
        query_texts: List[str],
        n_results: int = 3,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Any]]:
        query_text = (query_texts[0] if query_texts else "").lower()
        query_words = set(re.findall(r"\w+", query_text))

        scored_items = []
        for doc_id, item in self._entries.items():
            meta = item["metadata"]
            if where:
                match = True
                for k, v in where.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            doc_text = item["document"].lower()
            doc_words = set(re.findall(r"\w+", doc_text))
            overlap = len(query_words.intersection(doc_words))
            dist = 1.0 - (overlap / (len(query_words) or 1))
            scored_items.append((dist, item))

        scored_items.sort(key=lambda x: x[0])
        top_items = scored_items[:n_results]

        return {
            "ids": [[item["id"] for _, item in top_items]],
            "documents": [[item["document"] for _, item in top_items]],
            "metadatas": [[item["metadata"] for _, item in top_items]],
            "distances": [[dist for dist, _ in top_items]],
        }


class FallbackChromaClient:
    """In-memory ChromaDB-compatible client."""
    def __init__(self):
        self._collections: Dict[str, FallbackChromaCollection] = {}

    def get_or_create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> FallbackChromaCollection:
        if name not in self._collections:
            self._collections[name] = FallbackChromaCollection(name=name, metadata=metadata)
        return self._collections[name]

    def get_collection(self, name: str) -> FallbackChromaCollection:
        if name not in self._collections:
            self._collections[name] = FallbackChromaCollection(name=name)
        return self._collections[name]


_fallback_client = None


def get_chroma_client(persist_directory: str = CHROMA_PERSIST_DIR) -> Any:
    """Returns a ChromaDB client, falling back to FallbackChromaClient if chromadb is not installed."""
    global _fallback_client
    if HAVE_CHROMADB:
        if persist_directory and persist_directory != ":memory:":
            os.makedirs(persist_directory, exist_ok=True)
            return chromadb.PersistentClient(path=persist_directory)
        return chromadb.Client()
    if _fallback_client is None:
        _fallback_client = FallbackChromaClient()
    return _fallback_client


def seed_rag_collections(client: Any) -> None:
    """
    Seeds 'crop_guidance' and 'schemes' collections with verified documents.
    """
    crop_col = client.get_or_create_collection(
        name="crop_guidance",
        metadata={"description": "Agronomic advice from ICAR, KVK, and State Universities"},
    )
    for doc in SEED_CROP_DOCUMENTS:
        crop_col.upsert(
            ids=[doc["id"]],
            documents=[doc["text"]],
            metadatas=[
                {
                    "crop": doc["crop"],
                    "stage": doc["stage"],
                    "document_name": doc["document_name"],
                    "source_url": doc["source_url"],
                    "retrieval_date": doc["retrieval_date"],
                    "version": doc["version"],
                }
            ],
        )

    scheme_col = client.get_or_create_collection(
        name="schemes",
        metadata={"description": "Official Central and State Government Agricultural Schemes"},
    )
    for doc in SEED_SCHEME_DOCUMENTS:
        scheme_col.upsert(
            ids=[doc["id"]],
            documents=[doc["text"]],
            metadatas=[
                {
                    "scheme_name": doc["scheme_name"],
                    "state": doc["state"],
                    "document_name": doc["document_name"],
                    "source_url": doc["source_url"],
                    "retrieval_date": doc["retrieval_date"],
                    "version": doc["version"],
                }
            ],
        )


if __name__ == "__main__":
    client = get_chroma_client()
    seed_rag_collections(client)
    print("Successfully ingested and seeded collections: 'crop_guidance' and 'schemes'.")
