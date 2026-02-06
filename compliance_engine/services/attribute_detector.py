"""
Attribute Detection Service
===========================
Detects specific data attributes (health, financial, biometric, etc.)
from metadata using keywords, patterns, and configurations.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from dataclasses import dataclass

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of attribute detection"""
    detected: bool
    attribute_name: str
    detection_method: str  # keyword, pattern, category
    matched_terms: List[str]
    confidence: float


class AttributeDetectionConfig:
    """Configuration for detecting a specific attribute type"""

    def __init__(
        self,
        name: str,
        keywords: List[str] = None,
        patterns: List[str] = None,
        categories: List[str] = None,
        case_sensitive: bool = False,
        word_boundaries: bool = True,
        enabled: bool = True
    ):
        self.name = name
        self.keywords = set(k.lower() if not case_sensitive else k for k in (keywords or []))
        self.patterns = [re.compile(p, re.IGNORECASE if not case_sensitive else 0) for p in (patterns or [])]
        self.categories = set(c.lower() for c in (categories or []))
        self.case_sensitive = case_sensitive
        self.word_boundaries = word_boundaries
        self.enabled = enabled


class AttributeDetector:
    """
    Detects attributes from metadata using configurable rules.
    Supports keyword matching, regex patterns, and category lookups.
    """

    _instance: Optional['AttributeDetector'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._configs: Dict[str, AttributeDetectionConfig] = {}
        self._load_default_configs()
        self._load_config_files()
        self._initialized = True
        logger.info(f"Attribute detector initialized with {len(self._configs)} configurations")

    def _load_default_configs(self):
        """Load default attribute detection configurations"""
        # Health data detection
        self._configs['health_data'] = AttributeDetectionConfig(
            name='health_data',
            keywords=[
                # Medical conditions
                'diagnosis', 'treatment', 'medication', 'prescription',
                'symptom', 'disease', 'illness', 'condition', 'medical',
                'health', 'clinical', 'patient', 'hospital', 'doctor',
                'physician', 'nurse', 'healthcare', 'therapy', 'surgery',
                # Health records
                'medical_record', 'health_record', 'ehr', 'emr', 'phi',
                'protected_health_information', 'hipaa', 'health_insurance',
                # Body/physical
                'blood', 'vital', 'heart_rate', 'blood_pressure', 'bmi',
                'weight', 'height', 'temperature', 'pulse', 'respiratory',
                # Mental health
                'mental_health', 'psychiatric', 'psychology', 'anxiety',
                'depression', 'counseling', 'therapy',
                # Lab/test results
                'lab_result', 'test_result', 'biopsy', 'mri', 'xray',
                'ct_scan', 'ultrasound', 'imaging',
                # Specialized
                'allergy', 'immunization', 'vaccine', 'vaccination',
                'genetic', 'dna', 'genome', 'hereditary',
            ],
            patterns=[
                r'ICD[-_]?\d+',  # ICD codes
                r'CPT[-_]?\d+',  # CPT codes
                r'patient[-_]?id',
                r'medical[-_]?record[-_]?number',
                r'mrn[-_]?\d+',
                r'health[-_]?data',
                r'clinical[-_]?data',
            ],
            categories=['health', 'medical', 'clinical', 'patient'],
            enabled=True
        )

        # Financial data detection
        self._configs['financial_data'] = AttributeDetectionConfig(
            name='financial_data',
            keywords=[
                'bank_account', 'account_number', 'routing_number',
                'credit_card', 'debit_card', 'card_number', 'cvv', 'cvc',
                'financial', 'payment', 'transaction', 'balance',
                'loan', 'mortgage', 'investment', 'portfolio',
                'salary', 'income', 'tax', 'revenue', 'profit',
                'bank', 'banking', 'credit', 'debit', 'wire_transfer',
                'iban', 'swift', 'bic', 'ach',
            ],
            patterns=[
                r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Card numbers
                r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,}\b',  # IBAN
                r'account[-_]?num',
                r'routing[-_]?num',
            ],
            categories=['financial', 'banking', 'payment'],
            enabled=True
        )

        # Biometric data detection
        self._configs['biometric_data'] = AttributeDetectionConfig(
            name='biometric_data',
            keywords=[
                'fingerprint', 'facial_recognition', 'face_scan',
                'retina', 'iris', 'iris_scan', 'voice_print',
                'voiceprint', 'biometric', 'palm_print', 'hand_geometry',
                'gait', 'keystroke_dynamics', 'dna', 'genetic',
            ],
            patterns=[
                r'biometric[-_]?id',
                r'finger[-_]?print',
                r'face[-_]?id',
                r'touch[-_]?id',
            ],
            categories=['biometric', 'identity'],
            enabled=True
        )

        # Location data detection
        self._configs['location_data'] = AttributeDetectionConfig(
            name='location_data',
            keywords=[
                'gps', 'geolocation', 'coordinates', 'latitude', 'longitude',
                'location', 'address', 'postal_code', 'zip_code',
                'city', 'region', 'country', 'place', 'venue',
                'tracking', 'whereabouts',
            ],
            patterns=[
                r'lat[-_]?long',
                r'geo[-_]?location',
                r'\b-?\d{1,3}\.\d+,\s*-?\d{1,3}\.\d+\b',  # Coordinates
            ],
            categories=['location', 'geographic'],
            enabled=True
        )

    def _load_config_files(self):
        """Load configuration files from the config directory"""
        config_dir = settings.paths.config_dir

        # Try to load health_data_config.json - this extends the default health_data config
        health_config_path = config_dir / 'health_data_config.json'
        if health_config_path.exists():
            try:
                with open(health_config_path, 'r') as f:
                    config = json.load(f)

                    # Check if config is enabled
                    if not config.get('enabled', True):
                        logger.info("Health data config is disabled")
                    else:
                        # Create or update health_data config from file
                        keywords = config.get('keywords', [])
                        patterns = config.get('patterns', [])
                        categories = config.get('categories', [])

                        # If we already have a default config, merge with it
                        if 'health_data' in self._configs:
                            existing = self._configs['health_data']
                            existing.keywords.update(k.lower() for k in keywords)
                            for p in patterns:
                                try:
                                    existing.patterns.append(re.compile(p, re.IGNORECASE))
                                except re.error:
                                    logger.warning(f"Invalid pattern in health_data_config: {p}")
                            existing.categories.update(c.lower() for c in categories)
                        else:
                            # Create new config from file
                            self._configs['health_data'] = AttributeDetectionConfig(
                                name='health_data',
                                keywords=keywords,
                                patterns=patterns,
                                categories=categories,
                                case_sensitive=config.get('detection_settings', {}).get('case_sensitive', False),
                                word_boundaries=config.get('detection_settings', {}).get('word_boundaries', True),
                                enabled=True
                            )

                logger.info(f"Loaded health data config from {health_config_path}")
            except Exception as e:
                logger.error(f"Error loading health_data_config.json: {e}")

        # Load generic metadata detection config
        metadata_config_path = config_dir / 'metadata_detection_config.json'
        if metadata_config_path.exists():
            try:
                with open(metadata_config_path, 'r') as f:
                    config = json.load(f)
                    for category_name, category_config in config.get('detection_categories', {}).items():
                        if category_config.get('enabled', True):
                            self._configs[category_name] = AttributeDetectionConfig(
                                name=category_name,
                                keywords=category_config.get('keywords', []),
                                patterns=category_config.get('patterns', []),
                                categories=category_config.get('categories', []),
                                case_sensitive=category_config.get('case_sensitive', False),
                                word_boundaries=category_config.get('word_boundaries', True),
                                enabled=True
                            )
                logger.info(f"Loaded metadata detection config from {metadata_config_path}")
            except Exception as e:
                logger.error(f"Error loading metadata_detection_config.json: {e}")

    def add_config(self, config: AttributeDetectionConfig):
        """Add or update an attribute detection configuration"""
        self._configs[config.name] = config
        logger.info(f"Added/updated attribute detection config: {config.name}")

    def detect(
        self,
        metadata: Dict[str, Any],
        attribute_name: Optional[str] = None
    ) -> List[DetectionResult]:
        """
        Detect attributes in the provided metadata.

        Args:
            metadata: Dictionary of metadata to check
            attribute_name: Specific attribute to detect (None = check all)

        Returns:
            List of DetectionResult for each detected attribute
        """
        results = []

        configs_to_check = (
            {attribute_name: self._configs[attribute_name]}
            if attribute_name and attribute_name in self._configs
            else self._configs
        )

        # Convert metadata to searchable text
        search_text = self._metadata_to_text(metadata)
        search_text_lower = search_text.lower()

        for name, config in configs_to_check.items():
            if not config.enabled:
                continue

            result = self._detect_single(search_text, search_text_lower, config)
            if result.detected:
                results.append(result)

        return results

    def _detect_single(
        self,
        text: str,
        text_lower: str,
        config: AttributeDetectionConfig
    ) -> DetectionResult:
        """Detect a single attribute type"""
        matched_terms: Set[str] = set()
        detection_method = None

        # Check keywords
        for keyword in config.keywords:
            check_text = text if config.case_sensitive else text_lower
            if config.word_boundaries:
                # Use word boundary check
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, check_text, re.IGNORECASE if not config.case_sensitive else 0):
                    matched_terms.add(keyword)
                    detection_method = 'keyword'
            else:
                if keyword in check_text:
                    matched_terms.add(keyword)
                    detection_method = 'keyword'

        # Check patterns
        for pattern in config.patterns:
            matches = pattern.findall(text)
            if matches:
                matched_terms.update(str(m) for m in matches[:5])  # Limit matches
                detection_method = detection_method or 'pattern'

        # Calculate confidence based on number of matches
        confidence = min(1.0, len(matched_terms) / 3.0) if matched_terms else 0.0

        return DetectionResult(
            detected=bool(matched_terms),
            attribute_name=config.name,
            detection_method=detection_method or 'none',
            matched_terms=list(matched_terms)[:10],  # Limit returned terms
            confidence=confidence
        )

    def _metadata_to_text(self, metadata: Dict[str, Any]) -> str:
        """Convert metadata dictionary to searchable text"""
        parts = []

        def extract(obj, prefix=''):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    extract(v, f"{prefix}{k} ")
            elif isinstance(obj, list):
                for item in obj:
                    extract(item, prefix)
            elif obj is not None:
                parts.append(f"{prefix}{str(obj)}")

        extract(metadata)
        return ' '.join(parts)

    def detect_health_data(self, metadata: Dict[str, Any]) -> DetectionResult:
        """Convenience method to detect health data specifically"""
        results = self.detect(metadata, 'health_data')
        if results:
            return results[0]
        return DetectionResult(
            detected=False,
            attribute_name='health_data',
            detection_method='none',
            matched_terms=[],
            confidence=0.0
        )

    def detect_financial_data(self, metadata: Dict[str, Any]) -> DetectionResult:
        """Convenience method to detect financial data specifically"""
        results = self.detect(metadata, 'financial_data')
        if results:
            return results[0]
        return DetectionResult(
            detected=False,
            attribute_name='financial_data',
            detection_method='none',
            matched_terms=[],
            confidence=0.0
        )

    def get_supported_attributes(self) -> List[str]:
        """Get list of supported attribute types"""
        return [name for name, config in self._configs.items() if config.enabled]


# Singleton instance
_detector: Optional[AttributeDetector] = None


def get_attribute_detector() -> AttributeDetector:
    """Get the attribute detector instance"""
    global _detector
    if _detector is None:
        _detector = AttributeDetector()
    return _detector
